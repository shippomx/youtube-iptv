from app.db.models import Channel


def test_m3u_empty(client):
    resp = client.get("/m3u")
    assert resp.status_code == 200
    assert resp.text.startswith("#EXTM3U")


def test_m3u_includes_ok_channel(client, db_session):
    ch = Channel(
        name="TVBS",
        source_url="https://youtube.com/watch?v=aaa",
        stream_url="https://cdn.example.com/stream.m3u8",
        group_name="新闻",
        logo_url="https://logo.example.com/tvbs.png",
        enabled=True,
        status="ok",
    )
    db_session.add(ch)
    db_session.commit()

    resp = client.get("/m3u")
    assert resp.status_code == 200
    assert "TVBS" in resp.text
    assert "/proxy/" in resp.text
    assert 'group-title="新闻"' in resp.text
    assert 'tvg-logo="https://logo.example.com/tvbs.png"' in resp.text


def test_m3u_excludes_null_stream_url(client, db_session):
    ch = Channel(
        name="CNN",
        source_url="https://youtube.com/watch?v=bbb",
        stream_url=None,
        enabled=True,
        status="unknown",
    )
    db_session.add(ch)
    db_session.commit()

    resp = client.get("/m3u")
    assert "CNN" not in resp.text


def test_m3u_excludes_dead_channel_by_default(client, db_session):
    ch = Channel(
        name="BBC",
        source_url="https://youtube.com/watch?v=ccc",
        stream_url="https://cdn.example.com/bbc.m3u8",
        enabled=True,
        status="dead",
    )
    db_session.add(ch)
    db_session.commit()

    resp = client.get("/m3u")
    assert "BBC" not in resp.text


def test_m3u_include_dead_param(client, db_session):
    ch = Channel(
        name="BBC",
        source_url="https://youtube.com/watch?v=ccc",
        stream_url="https://cdn.example.com/bbc.m3u8",
        enabled=True,
        status="dead",
    )
    db_session.add(ch)
    db_session.commit()

    resp = client.get("/m3u?include_dead=true")
    assert "BBC" in resp.text
    assert "/proxy/" in resp.text


def test_m3u_excludes_disabled_channel(client, db_session):
    ch = Channel(
        name="Sky",
        source_url="https://youtube.com/watch?v=ddd",
        stream_url="https://cdn.example.com/sky.m3u8",
        enabled=False,
        status="ok",
    )
    db_session.add(ch)
    db_session.commit()

    resp = client.get("/m3u")
    assert "Sky" not in resp.text
