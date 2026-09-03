import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

import jwt
import requests
from flask import current_app, session


@dataclass(frozen=True)
class OAuthIdentity:
    provider: str
    subject: str
    email: str | None
    email_verified: bool
    name: str | None


class OAuthProviderError(RuntimeError):
    """A configured OAuth provider could not complete an upstream operation."""


PROVIDERS = {
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "jwks": "https://www.googleapis.com/oauth2/v3/certs",
        "issuer": "https://accounts.google.com",
        "scope": "openid email profile",
        "oidc": True,
    },
    "github": {
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "scope": "read:user user:email",
        "oidc": False,
    },
    "apple": {
        "authorize": "https://appleid.apple.com/auth/authorize",
        "token": "https://appleid.apple.com/auth/token",
        "jwks": "https://appleid.apple.com/auth/keys",
        "issuer": "https://appleid.apple.com",
        "scope": "name email",
        "oidc": True,
    },
    "microsoft": {
        "authorize": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "jwks": "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys",
        "issuer": "https://login.microsoftonline.com/{tenant}/v2.0",
        "scope": "openid email profile",
        "oidc": True,
    },
}


def _config(provider):
    if provider not in PROVIDERS:
        raise ValueError("Unsupported OAuth provider.")
    prefix = provider.upper()
    client_id = current_app.config.get(f"{prefix}_OAUTH_CLIENT_ID")
    redirect_uri = current_app.config.get(f"{prefix}_OAUTH_REDIRECT_URI")
    required = [client_id, redirect_uri]
    if provider == "apple":
        required.extend(current_app.config.get(key) for key in ("APPLE_TEAM_ID", "APPLE_KEY_ID", "APPLE_PRIVATE_KEY"))
    else:
        required.append(current_app.config.get(f"{prefix}_OAUTH_CLIENT_SECRET"))
    if provider == "microsoft":
        required.append(current_app.config.get("MICROSOFT_OAUTH_TENANT"))
    if not all(required):
        raise RuntimeError(f"{provider.title()} OAuth is not configured.")
    parsed_redirect = urlsplit(redirect_uri)
    if parsed_redirect.scheme not in {"http", "https"} or not parsed_redirect.netloc or parsed_redirect.fragment:
        raise RuntimeError(f"{provider.title()} OAuth redirect URI is invalid.")
    if current_app.config.get("IS_PRODUCTION") and parsed_redirect.scheme != "https":
        raise RuntimeError(f"{provider.title()} OAuth redirect URI must use HTTPS.")
    config = dict(PROVIDERS[provider])
    tenant = current_app.config.get("MICROSOFT_OAUTH_TENANT", "")
    if provider == "microsoft":
        if not tenant:
            raise RuntimeError("Microsoft OAuth tenant is not configured.")
        config = {key: value.format(tenant=tenant) if isinstance(value, str) else value for key, value in config.items()}
    config.update({"client_id": client_id, "redirect_uri": redirect_uri})
    return config


def provider_is_configured(provider):
    try:
        _config(provider)
        return True
    except (RuntimeError, ValueError):
        return False


def _pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def begin_authorization(provider, link_user_id=None):
    config = _config(provider)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    session[f"oauth_{provider}"] = {
        "state": state,
        "nonce": nonce,
        "verifier": verifier,
        "link_user_id": str(link_user_id) if link_user_id else None,
        "created_at": int(time.time()),
    }
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
        "code_challenge": _pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    if config["oidc"]:
        params["nonce"] = nonce
    if provider == "apple":
        params["response_mode"] = "form_post"
    return f"{config['authorize']}?{urlencode(params)}"


def _apple_client_secret(client_id):
    team_id = current_app.config.get("APPLE_TEAM_ID")
    key_id = current_app.config.get("APPLE_KEY_ID")
    private_key = current_app.config.get("APPLE_PRIVATE_KEY")
    if not team_id or not key_id or not private_key:
        raise RuntimeError("Apple OAuth signing credentials are not configured.")
    private_key = private_key.replace("\\n", "\n")
    now = int(time.time())
    return jwt.encode(
        {"iss": team_id, "iat": now, "exp": now + 300, "aud": "https://appleid.apple.com", "sub": client_id},
        private_key,
        algorithm="ES256",
        headers={"kid": key_id},
    )


def _client_secret(provider, config):
    if provider == "apple":
        return _apple_client_secret(config["client_id"])
    return current_app.config.get(f"{provider.upper()}_OAUTH_CLIENT_SECRET")


def _verified_oidc_identity(provider, config, id_token, nonce):
    try:
        key = jwt.PyJWKClient(
            config["jwks"], timeout=current_app.config.get("OAUTH_HTTP_TIMEOUT_SECONDS", 10)
        ).get_signing_key_from_jwt(id_token).key
    except jwt.PyJWKClientConnectionError as error:
        raise OAuthProviderError("OAUTH_PROVIDER_UNAVAILABLE") from error
    claims = jwt.decode(
        id_token,
        key,
        algorithms=["RS256", "ES256"],
        audience=config["client_id"],
        issuer=config["issuer"],
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValueError("OAuth nonce validation failed.")
    email = claims.get("email") or claims.get("preferred_username")
    verified = claims.get("email_verified") is True
    if provider == "microsoft" and email:
        verified = True  # Microsoft signs the tenant identity and preferred_username claim.
    return OAuthIdentity(provider, str(claims["sub"]), email.lower() if email else None, verified, claims.get("name"))


def _github_identity(access_token):
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
    timeout = current_app.config.get("OAUTH_HTTP_TIMEOUT_SECONDS", 10)
    try:
        user_response = requests.get("https://api.github.com/user", headers=headers, timeout=timeout)
        user_response.raise_for_status()
        profile = user_response.json()
        emails_response = requests.get("https://api.github.com/user/emails", headers=headers, timeout=timeout)
        emails_response.raise_for_status()
        emails = emails_response.json()
    except requests.RequestException as error:
        raise OAuthProviderError("OAUTH_PROVIDER_UNAVAILABLE") from error
    verified = next((item for item in emails if item.get("primary") and item.get("verified")), None)
    email = verified.get("email").lower() if verified and verified.get("email") else None
    return OAuthIdentity("github", str(profile["id"]), email, bool(email), profile.get("name") or profile.get("login"))


def complete_authorization(provider, code, state):
    config = _config(provider)
    flow = session.pop(f"oauth_{provider}", None)
    if not flow or int(time.time()) - int(flow.get("created_at", 0)) > 600:
        raise ValueError("OAuth flow expired or was not initiated.")
    if not state or not secrets.compare_digest(str(state), str(flow.get("state", ""))):
        raise ValueError("OAuth state validation failed.")
    if not isinstance(code, str) or not code or len(code) > 2048:
        raise ValueError("OAuth authorization code is invalid.")
    secret = _client_secret(provider, config)
    if not secret:
        raise RuntimeError(f"{provider.title()} OAuth client secret is not configured.")
    payload = {
        "client_id": config["client_id"],
        "client_secret": secret,
        "code": code,
        "redirect_uri": config["redirect_uri"],
        "grant_type": "authorization_code",
        "code_verifier": flow["verifier"],
    }
    timeout = current_app.config.get("OAUTH_HTTP_TIMEOUT_SECONDS", 10)
    try:
        response = requests.post(config["token"], data=payload, headers={"Accept": "application/json"}, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as error:
        raise OAuthProviderError("OAUTH_PROVIDER_UNAVAILABLE") from error
    tokens = response.json()
    if tokens.get("error"):
        raise ValueError("OAuth provider rejected the authorization code.")
    if provider == "github":
        identity = _github_identity(tokens.get("access_token"))
    else:
        if not tokens.get("id_token"):
            raise ValueError("OAuth provider did not return an ID token.")
        identity = _verified_oidc_identity(provider, config, tokens["id_token"], flow["nonce"])
    return identity, flow.get("link_user_id")
