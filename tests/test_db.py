from app.db.models import Channel


def test_create_channel(db_session):
    ch = Channel(name="TVBS", source_url="https://youtube.com/watch?v=xxx")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    assert ch.id is not None
    assert ch.name == "TVBS"
    assert ch.status == "unknown"
    assert ch.enabled is True
    assert ch.fail_count == 0
    assert ch.stream_url is None


def test_channel_defaults(db_session):
    ch = Channel(name="CNN", source_url="https://youtube.com/watch?v=yyy")
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)

    assert ch.group_name == "default"
    assert ch.logo_url is None
    assert ch.last_check is None
