from app.db.models import Channel


def test_health_empty(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["total_channels"] == 0
    assert data["channels"] == []


def test_health_with_channels(client, db_session):
    db_session.add(Channel(name="TVBS", source_url="https://youtube.com/watch?v=aaa", status="ok"))
    db_session.add(Channel(name="CNN", source_url="https://youtube.com/watch?v=bbb", status="dead"))
    db_session.commit()

    resp = client.get("/health")
    data = resp.json()
    assert data["total_channels"] == 2
    assert data["ok_count"] == 1
    assert data["dead_count"] == 1
    assert len(data["channels"]) == 2
