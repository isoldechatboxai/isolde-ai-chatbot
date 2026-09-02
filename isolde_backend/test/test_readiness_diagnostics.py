from app import _readiness_error_category


def test_readiness_error_categories_are_safe_and_actionable():
    assert _readiness_error_category(RuntimeError("connection refused by host.example.test")) == "NETWORK_ERROR"
    assert _readiness_error_category(RuntimeError("operation timed out")) == "TIMEOUT"
    assert _readiness_error_category(RuntimeError("Access Denied")) == "ACCESS_DENIED"
    assert _readiness_error_category(RuntimeError("No credentials available")) == "AUTHENTICATION_ERROR"
    assert _readiness_error_category(RuntimeError("NoSuchBucket")) == "BUCKET_NOT_FOUND"
