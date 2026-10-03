import pytest
from unittest.mock import patch


def test_history_requires_authorization(client):
    resp = client.get("/api/history")
    assert resp.status_code == 401
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "authentication_error"


def test_history_list_authenticated(client):
    fake_history = [
        {
            "analysis_id": "test-id-1",
            "createdAt": "2026-09-25T00:00:00Z",
            "job": {"title": "Software Engineer"},
            "score": 85,
        }
    ]
    with patch("utils.auth.verify_id_token", return_value="uid-456"), \
         patch("services.firebase_service.list_history", return_value=fake_history):
        resp = client.get("/api/history", headers={"Authorization": "Bearer fake-token"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["history"]) == 1
    assert data["history"][0]["analysis_id"] == "test-id-1"


def test_get_history_item_authenticated(client):
    fake_item = {
        "analysis_id": "test-id-1",
        "job": {"title": "Software Engineer"},
        "score": {"overall": 85},
    }
    with patch("utils.auth.verify_id_token", return_value="uid-456"), \
         patch("services.firebase_service.get_analysis", return_value=fake_item):
        resp = client.get("/api/history/test-id-1", headers={"Authorization": "Bearer fake-token"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["analysis"]["analysis_id"] == "test-id-1"


def test_delete_history_item_authenticated(client):
    with patch("utils.auth.verify_id_token", return_value="uid-456"), \
         patch("services.firebase_service.delete_analysis") as mock_del:
        resp = client.delete("/api/history/test-id-1", headers={"Authorization": "Bearer fake-token"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["deleted"] == "test-id-1"
    mock_del.assert_called_once_with("uid-456", "test-id-1")


def test_auth_profile_authenticated(client):
    with patch("utils.auth.verify_id_token", return_value="uid-456"), \
         patch("services.firebase_service.upsert_profile", return_value={"displayName": "Jane", "email": "jane@example.com"}):
        resp = client.post(
            "/api/auth/profile",
            json={"displayName": "Jane", "email": "jane@example.com"},
            headers={"Authorization": "Bearer fake-token"},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["profile"]["displayName"] == "Jane"
