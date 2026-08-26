"""
Phase 3 regression tests — SaaS API-key service/route integration.

Coverage:
  1. New key generation creates key_hash.
  2. New key generation creates key_prefix.
  3. Raw key verifies against key_hash.
  4. Wrong raw key fails verification.
  5. to_dict() never exposes key_secret.
  6. to_dict() never exposes key_hash.
  7. No raw secret fragment appears in serialized output.
  8. Existing list route remains compatible (safe serialization).
  9. Legacy rows (key_hash NULL) do not crash verification.

Model-level tests run without a database. Verification/route tests rely on
the project's existing `app` and `client` fixtures.
"""
import pytest

from app.models.saas_cloud_model import APIKey
from app.models.user import User
from flask_jwt_extended import create_access_token


def _authenticated_user(db):
    user = User(name="SaaS User", email="saas@example.com", status="Active")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user, {"Authorization": f"Bearer {create_access_token(identity=user.id)}"}


# ---------------------------------------------------------------------------
# Model-level: generation, hashing, serialization (no DB required)
# ---------------------------------------------------------------------------

def test_generate_key_creates_key_hash():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    assert key_hash is not None
    assert isinstance(key_hash, str)
    assert len(key_hash) > 0


def test_generate_key_creates_key_prefix():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    assert key_prefix is not None
    assert isinstance(key_prefix, str)
    assert len(key_prefix) > 0


def test_generate_key_hash_corresponds_to_raw_key():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    assert APIKey.hash_key(raw_key) == key_hash


def test_key_hash_is_not_the_raw_key():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    assert key_hash != raw_key
    # The raw key material must not be recoverable from / visible in the hash.
    assert raw_key not in key_hash


def test_key_prefix_is_a_true_prefix_and_shorter_than_secret():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    assert raw_key.startswith(key_prefix)
    assert len(key_prefix) < len(raw_key)


def test_generated_keys_are_unique():
    raw_a, hash_a, _ = APIKey.generate_key()
    raw_b, hash_b, _ = APIKey.generate_key()
    assert raw_a != raw_b
    assert hash_a != hash_b


def _make_key(raw_key, key_hash, key_prefix, **overrides):
    defaults = dict(
        id=1,
        user_id=1,
        key_name="phase3",
        key_secret=raw_key,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes="read,write,ai",
        is_active=True,
    )
    defaults.update(overrides)
    return APIKey(**defaults)


def test_to_dict_never_exposes_key_secret():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    data = _make_key(raw_key, key_hash, key_prefix).to_dict()
    assert "key_secret" not in data


def test_to_dict_never_exposes_key_hash():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    data = _make_key(raw_key, key_hash, key_prefix).to_dict()
    assert "key_hash" not in data


def test_to_dict_contains_no_raw_secret_fragment():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    data = _make_key(raw_key, key_hash, key_prefix).to_dict()
    serialized = str(data)
    # Secret material beyond the safe prefix must not leak.
    secret_tail = raw_key[len(key_prefix):]
    assert secret_tail not in serialized
    # The hash must not leak either.
    assert key_hash not in serialized


def test_to_dict_exposes_only_safe_metadata():
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    data = _make_key(raw_key, key_hash, key_prefix, id=7, user_id=3).to_dict()
    assert data["id"] == 7
    assert data["user_id"] == 3
    assert data["key_name"] == "phase3"
    assert data["key_prefix"] == key_prefix
    assert data["scopes"] == "read,write,ai"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# Verification + legacy behavior (require the app / test database fixtures)
# ---------------------------------------------------------------------------

def test_verify_key_accepts_valid_raw_key(app):
    from app.extensions import db
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    key = APIKey(
        user_id=1, key_name="phase3-verify",
        key_secret=raw_key, key_hash=key_hash, key_prefix=key_prefix,
        scopes="read,write,ai", is_active=True,
    )
    db.session.add(key)
    db.session.commit()

    found = APIKey.verify_key(raw_key)
    assert found is not None
    assert found.id == key.id


def test_verify_key_rejects_wrong_raw_key(app):
    from app.extensions import db
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    key = APIKey(
        user_id=1, key_name="phase3-verify-wrong",
        key_secret=raw_key, key_hash=key_hash, key_prefix=key_prefix,
        scopes="read,write,ai", is_active=True,
    )
    db.session.add(key)
    db.session.commit()

    assert APIKey.verify_key("isk_totally_wrong_key_value") is None


def test_verify_key_rejects_inactive_key(app):
    from app.extensions import db
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    key = APIKey(
        user_id=1, key_name="phase3-inactive",
        key_secret=raw_key, key_hash=key_hash, key_prefix=key_prefix,
        scopes="read,write,ai", is_active=False,
    )
    db.session.add(key)
    db.session.commit()

    assert APIKey.verify_key(raw_key) is None


def test_verify_key_does_not_crash_on_legacy_null_hash(app):
    from app.extensions import db
    # Simulate a legacy row that still has key_secret but no key_hash.
    legacy = APIKey(
        user_id=1, key_name="phase3-legacy",
        key_secret="isk_legacy_secret_value_placeholder",
        key_hash=None, key_prefix=None,
        scopes="read,write,ai", is_active=True,
    )
    db.session.add(legacy)
    db.session.commit()

    # Must not raise even though key_hash is NULL. Hash-based verification
    # cannot match a NULL key_hash, so the result is None (no crash, no leak).
    assert APIKey.verify_key("isk_legacy_secret_value_placeholder") is None


# ---------------------------------------------------------------------------
# Route compatibility (requires the app test client fixture)
# ---------------------------------------------------------------------------

def test_list_api_keys_route_does_not_expose_secrets(app, client):
    from app.extensions import db
    user, headers = _authenticated_user(db)
    raw_key, key_hash, key_prefix = APIKey.generate_key()
    key = APIKey(
        user_id=user.id, key_name="phase3-list",
        key_secret=raw_key, key_hash=key_hash, key_prefix=key_prefix,
        scopes="read,write,ai", is_active=True,
    )
    db.session.add(key)
    db.session.commit()

    resp = client.get("/api/saas/apikeys", headers=headers)
    assert resp.status_code == 200
    serialized = str(resp.get_json())

    # Neither the stored secret nor the hash may appear in the list response.
    assert raw_key not in serialized
    assert key_hash not in serialized
    # The safe prefix may appear.
    assert key_prefix in serialized


def test_create_api_key_route_returns_raw_key_once_and_safe_metadata(app, client):
    from app.extensions import db
    _, headers = _authenticated_user(db)
    resp = client.post(
        "/api/saas/apikeys",
        json={"key_name": "phase3-create", "scopes": "read,write,ai"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()

    # The raw key is returned exactly once at creation.
    assert "raw_key" in body
    assert body["raw_key"].startswith("isk_")

    # The serialized api_key metadata must not contain the secret or the hash.
    metadata = body["api_key"]
    assert "key_secret" not in metadata
    assert "key_hash" not in metadata
    assert metadata.get("key_prefix")
    assert body["raw_key"] not in str(metadata)

    stored = APIKey.query.get(metadata["id"])
    assert stored.key_secret is None
