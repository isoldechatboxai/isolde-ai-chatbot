# tests/test_saas_apikey_phase2.py
import secrets
import pytest
from werkzeug.security import check_password_hash
from app.models.saas_cloud_model import APIKey

def test_generate_secure_key_returns_tuple():
    raw, prefix, hashed = APIKey.generate_secure_key()
    assert isinstance(raw, str)
    assert isinstance(prefix, str)
    assert isinstance(hashed, str)

def test_generate_secure_key_format():
    raw, prefix, hashed = APIKey.generate_secure_key()
    assert raw.startswith("isk_")
    assert len(raw) == 36  # "isk_" (4) + 32 hex chars
    assert prefix == raw[:12]
    assert len(prefix) == 12

def test_generate_secure_key_hash_verifies():
    raw, prefix, hashed = APIKey.generate_secure_key()
    assert check_password_hash(hashed, raw) is True
    assert check_password_hash(hashed, "wrong_key") is False

def test_generate_secure_key_uniqueness():
    raw1, _, hash1 = APIKey.generate_secure_key()
    raw2, _, hash2 = APIKey.generate_secure_key()
    assert raw1 != raw2
    assert hash1 != hash2

def test_to_dict_excludes_secrets():
    raw, prefix, hashed = APIKey.generate_secure_key()
    key = APIKey(
        id=1, user_id=1, key_name="test",
        key_prefix=prefix, key_hash=hashed, key_secret=None
    )
    data = key.to_dict()
    
    assert "key_secret" not in data
    assert "key_hash" not in data
    assert "raw_key" not in data
    
    # Ensure no fragment of the raw key (beyond the prefix) leaks
    secret_part = raw[12:]
    for value in data.values():
        if isinstance(value, str):
            assert secret_part not in value

def test_to_dict_includes_safe_metadata():
    raw, prefix, hashed = APIKey.generate_secure_key()
    key = APIKey(
        id=1, user_id=1, key_name="test",
        key_prefix=prefix, key_hash=hashed, key_secret=None
    )
    data = key.to_dict()
    
    assert data["key_prefix"] == prefix
    assert data["id"] == 1
    assert data["user_id"] == 1
    assert data["key_name"] == "test"