"""
Regression test for PHASE 1 of PART 3:
APIKey.to_dict() must NEVER expose secret material (full, partial, or prefixed).
"""
from app.models.saas_cloud_model import APIKey


def _make_key(**overrides):
    defaults = dict(
        id=1,
        user_id=42,
        key_name="regression-key",
        key_secret="isk_deadbeef1234567890abcdef",
        scopes="read,write,ai",
        is_active=True,
    )
    defaults.update(overrides)
    return APIKey(**defaults)


def test_apikey_to_dict_does_not_expose_key_secret():
    key = _make_key()
    data = key.to_dict()

    assert "key_secret" not in data, "key_secret must not be present in to_dict() output"


def test_apikey_to_dict_does_not_expose_key_hash():
    key = _make_key()
    data = key.to_dict()

    assert "key_hash" not in data, "key_hash must not be present in to_dict() output"


def test_apikey_to_dict_does_not_leak_partial_secret():
    key = _make_key(key_secret="isk_deadbeef1234567890abcdef")
    data = key.to_dict()

    # No string value in the output may contain any fragment of the raw secret.
    secret_fragments = ("isk_", "deadbeef", "1234567890", "abcdef")
    for field_name, value in data.items():
        if isinstance(value, str):
            for fragment in secret_fragments:
                assert fragment not in value, (
                    f"Field {field_name!r} leaks secret fragment {fragment!r}: {value!r}"
                )


def test_apikey_to_dict_preserves_safe_metadata():
    key = _make_key()
    data = key.to_dict()

    assert data["id"] == 1
    assert data["user_id"] == 42
    assert data["key_name"] == "regression-key"
    assert data["scopes"] == "read,write,ai"
    assert data["is_active"] is True
    # created_at may be None before flush; presence is not asserted here.
    assert "created_at" in data


def test_apikey_to_dict_with_empty_secret_does_not_expose():
    key = _make_key(key_secret="")
    data = key.to_dict()

    assert "key_secret" not in data
    assert "key_hash" not in data