import pytest
from fastapi.testclient import TestClient


def test_list_channels_empty(client):
    resp = client.get("/channels")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_channel(client):
    payload = {"name": "TVBS", "source_url": "https://youtube.com/watch?v=aaa"}
    resp = client.post("/channels", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "TVBS"
    assert data["status"] == "unknown"
    assert data["enabled"] is True


def test_create_channel_duplicate_source_url(client):
    payload = {"name": "TVBS", "source_url": "https://youtube.com/watch?v=aaa"}
    client.post("/channels", json=payload)
    resp = client.post("/channels", json=payload)
    assert resp.status_code == 409


def test_patch_channel(client):
    create_resp = client.post(
        "/channels",
        json={"name": "CNN", "source_url": "https://youtube.com/watch?v=bbb"},
    )
    ch_id = create_resp.json()["id"]
    resp = client.patch(f"/channels/{ch_id}", json={"name": "CNN HD", "enabled": False})
    assert resp.status_code == 200
    assert resp.json()["name"] == "CNN HD"
    assert resp.json()["enabled"] is False


def test_delete_channel(client):
    create_resp = client.post(
        "/channels",
        json={"name": "BBC", "source_url": "https://youtube.com/watch?v=ccc"},
    )
    ch_id = create_resp.json()["id"]
    resp = client.delete(f"/channels/{ch_id}")
    assert resp.status_code == 204
    assert client.get("/channels").json() == []


def test_delete_nonexistent_channel(client):
    resp = client.delete("/channels/999")
    assert resp.status_code == 404


def test_create_channel_duplicate_returns_detail(client):
    payload = {"name": "TVBS", "source_url": "https://youtube.com/watch?v=aaa"}
    client.post("/channels", json=payload)
    resp = client.post("/channels", json=payload)
    assert resp.status_code == 409
    assert "source_url" in resp.json()["detail"]


def test_refresh_channel_returns_202(client):
    create_resp = client.post(
        "/channels",
        json={"name": "TVBS", "source_url": "https://youtube.com/watch?v=aaa"},
    )
    ch_id = create_resp.json()["id"]
    resp = client.post(f"/channels/{ch_id}/refresh")
    assert resp.status_code == 202


def test_refresh_all_returns_202(client):
    resp = client.post("/channels/refresh-all")
    assert resp.status_code == 202


def test_refresh_nonexistent_channel(client):
    resp = client.post("/channels/999/refresh")
    assert resp.status_code == 404
