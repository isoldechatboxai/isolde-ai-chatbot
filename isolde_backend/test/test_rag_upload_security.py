import io


def _token(client, email):
    client.post("/api/register", json={
        "name": "RAG User", "email": email, "password": "StrongPass123!",
    })
    return client.post("/api/login", json={
        "email": email, "password": "StrongPass123!",
    }).get_json()["access_token"]


def test_rag_upload_rejects_null_byte_filename(client):
    token = _token(client, "rag-null@example.com")

    response = client.post(
        "/api/rag/upload", headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"safe text"), "document.txt\x00.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "Invalid filename."


def test_rag_upload_uses_safe_bounded_filename(client, monkeypatch):
    token = _token(client, "rag-filename@example.com")
    captured = {}

    def index_file(path, filename, user_id):
        captured.update({"path": path, "filename": filename, "user_id": user_id})
        return 1

    monkeypatch.setattr("app.routes.rag_routes.process_and_index_file", index_file)
    filename = "../" + ("a" * 300) + ".txt"
    response = client.post(
        "/api/rag/upload", headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"safe text"), filename)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert ".." not in captured["filename"]
    assert len(captured["filename"]) <= 220


def test_rag_upload_rejects_mismatched_declared_mime_type(client):
    token = _token(client, "rag-mime@example.com")
    response = client.post(
        "/api/rag/upload", headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"plain text"), "document.pdf", "text/plain")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["message"] == "File MIME type does not match its extension."


def test_rag_upload_enforces_streamed_byte_limit(client, app):
    app.config["RAG_MAX_UPLOAD_BYTES"] = 4
    token = _token(client, "rag-size@example.com")
    response = client.post(
        "/api/rag/upload", headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"five!"), "document.txt", "text/plain")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 413
    assert response.get_json()["message"] == "File too large."
