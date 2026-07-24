import re
from html import escape

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_REGEX.match(email))


def is_valid_password(password: str) -> tuple[bool, str]:
    """Basic password strength check. Returns (is_valid, reason)."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    return True, ""


def sanitize_text(text: str) -> str:
    """Escape HTML to mitigate stored/reflected XSS from user-provided text."""
    if text is None:
        return ""
    return escape(text.strip())


def is_non_empty(value: str) -> bool:
    return isinstance(value, str) and len(value.strip()) > 0


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )
