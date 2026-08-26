import io


def _token(client, email):
    client.post("/api/register", json={
        "name": "Storage User", "email": email, "password": "StrongPass123!",
    })
    return client.post("/api/login", json={
        "email": email, "password": "StrongPass123!",
    }).get_json()["access_token"]


def test_private_local_upload_list_download_delete_and_ownership(client):
    first = _token(client, "files-one@example.com")
    second = _token(client, "files-two@example.com")
    first_headers = {"Authorization": f"Bearer {first}"}
    second_headers = {"Authorization": f"Bearer {second}"}

    uploaded = client.post(
        "/api/upload", headers=first_headers,
        data={"file": (io.BytesIO(b"private image bytes"), "photo.png")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201
    file_id = uploaded.get_json()["file"]["id"]

    listing = client.get("/api/uploads", headers=first_headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.get_json()["files"]] == [file_id]
    assert client.get(f"/api/uploads/{file_id}", headers=second_headers).status_code == 404
    assert client.delete(f"/api/uploads/{file_id}", headers=second_headers).status_code == 404

    download = client.get(f"/api/uploads/{file_id}", headers=first_headers)
    assert download.status_code == 200
    assert download.data == b"private image bytes"
    assert client.delete(f"/api/uploads/{file_id}", headers=first_headers).status_code == 200
    assert client.get(f"/api/uploads/{file_id}", headers=first_headers).status_code == 404


def test_s3_backend_without_bucket_fails_deterministically(client, app):
    token = _token(client, "storage-config@example.com")
    app.config.update({"STORAGE_BACKEND": "s3", "S3_BUCKET": ""})
    response = client.post(
        "/api/upload", headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"bytes"), "photo.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 503
    assert response.get_json()["error"] == "File storage is not configured."
