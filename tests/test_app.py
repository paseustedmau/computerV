import base64
import importlib

import cv2
import numpy as np
from fastapi.testclient import TestClient


def image_data_url():
    ok, encoded = cv2.imencode(".jpg", np.zeros((20, 20, 3), dtype=np.uint8))
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(encoded).decode()


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ATTENDANCE_DATA_DIR", str(tmp_path))
    import app.main as main
    main = importlib.reload(main)
    monkeypatch.setattr(main, "embedding_for", lambda image: [1.0, 0.0, 0.0])
    return TestClient(main.app)


def test_enroll_recognize_and_prevent_daily_duplicate(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    image = image_data_url()
    enrollment = client.post("/api/enroll", json={"name": "Ada Lovelace", "student_id": "a-01", "image": image})
    assert enrollment.status_code == 201
    assert enrollment.json()["person"]["student_id"] == "A-01"

    first = client.post("/api/recognize", json={"image": image})
    second = client.post("/api/recognize", json={"image": image})
    assert first.status_code == 200 and first.json()["already_present"] is False
    assert second.status_code == 200 and second.json()["already_present"] is True
    assert len(client.get("/api/attendance").json()) == 1


def test_rejects_invalid_image(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    response = client.post("/api/recognize", json={"image": "this-is-not-a-valid-image-payload"})
    assert response.status_code == 400


def test_unknown_face_does_not_create_attendance(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)
    image = image_data_url()
    client.post("/api/enroll", json={"name": "Grace Hopper", "student_id": "G01", "image": image})
    import app.main as main
    monkeypatch.setattr(main, "embedding_for", lambda current: [0.0, 1.0, 0.0])
    result = client.post("/api/recognize", json={"image": image})
    assert result.json()["recognized"] is False
    assert client.get("/api/attendance").json() == []
