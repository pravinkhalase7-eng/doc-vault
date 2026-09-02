from app.models.sharing import ShareLink, ShareLinkEvent


def test_share_link_id_is_unset_until_flush():
    link = ShareLink(user_id="11111111-1111-1111-1111-111111111111", token_hash="abc")
    assert link.id is None
    event = ShareLinkEvent(share_link_id=link.id, event="created")
    assert event.share_link_id is None
