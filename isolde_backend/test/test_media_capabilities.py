from flask_jwt_extended import create_access_token

from app.models.user import User


def _headers(db):
    user = User(name="Media User", email="media@example.com", status="Active")
    user.set_password("StrongPass123!")
    db.session.add(user)
    db.session.commit()
    return {"Authorization": f"Bearer {create_access_token(identity=user.id)}"}


def test_media_capabilities_never_fabricate_provider_readiness(client, app, db):
    headers = _headers(db)
    response = client.get("/api/studio/capabilities", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {
        "image": "NOT_CONFIGURED",
        "video": "NOT_CONFIGURED",
        "watermark": {
            "status": "NOT_APPLICABLE",
            "reason": "Watermarking is applied only by an implemented generated-media pipeline.",
        },
    }
    assert client.post("/api/studio/generate-image", headers=headers, json={"prompt": "test"}).status_code == 503
    assert client.post("/api/studio/generate-video", headers=headers, json={"prompt": "test"}).status_code == 503

    app.config["IMAGE_PROVIDER"] = "unknown"
    app.config["VIDEO_PROVIDER"] = "unknown"
    configured = client.get("/api/studio/capabilities", headers=headers).get_json()
    assert configured["image"] == "NOT_SUPPORTED"
    assert configured["video"] == "NOT_SUPPORTED"
