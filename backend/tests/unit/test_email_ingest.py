from types import SimpleNamespace

from app.email.ingest import (
    InboundAttachment,
    ingest_secret_ok,
    is_shared_inbox_recipient,
    keep_attachment,
    match_collection_for_ingest,
    normalize_subject,
    parse_ingest_recipient,
    sender_email,
    split_local_part,
)


def _col(name: str, id_: str | None = None):
    return SimpleNamespace(id=id_ or name.lower(), name=name, parent_id=None, extra={})


def test_normalize_subject_strips_fwd_prefixes():
    assert normalize_subject("Fwd: Re: Insurance renewal") == "Insurance renewal"
    assert normalize_subject("FW: Bills") == "Bills"


def test_parse_recipient_plus_tag():
    token, plus, domain = parse_ingest_recipient("DocVault <dvabc123def456+insurance@in.docvault.doxstation.com>")
    assert token == "dvabc123def456"
    assert plus == "insurance"
    assert domain == "in.docvault.doxstation.com"
    assert split_local_part("dvabc+bills") == ("dvabc", "bills")


def test_subject_picks_unique_collection():
    cols = [_col("Insurance"), _col("Bills"), _col("Education")]
    hit = match_collection_for_ingest(cols, subject="Fwd: Insurance policy 2026")
    assert hit.name == "Insurance"
    assert match_collection_for_ingest(cols, subject="HDFC Ergo") is None


def test_subject_prefers_longest_unique_name():
    cols = [_col("Insurance"), _col("Health Insurance")]
    hit = match_collection_for_ingest(cols, subject="Health Insurance renewal")
    assert hit.name == "Health Insurance"


def test_two_equal_length_matches_stay_unfiled():
    cols = [_col("Home"), _col("Work")]
    assert match_collection_for_ingest(cols, subject="Home and Work papers") is None


def test_plus_tag_beats_subject():
    cols = [_col("Insurance"), _col("Bills")]
    hit = match_collection_for_ingest(cols, subject="Insurance overdue", plus_tag="bills")
    assert hit.name == "Bills"


def test_bill_does_not_match_billing_word():
    cols = [_col("Bill")]
    assert match_collection_for_ingest(cols, subject="billing statement") is None
    assert match_collection_for_ingest(cols, subject="this Bill is due").name == "Bill"


def test_ingest_secret_compare():
    assert ingest_secret_ok("abc", "abc")
    assert not ingest_secret_ok("abc", "abd")
    assert not ingest_secret_ok("", "abc")
    assert not ingest_secret_ok("abc", "")


def test_keep_attachment_skips_tiny_inline_and_signatures():
    tiny = InboundAttachment("sig.png", b"\x89PNG\r\n\x1a\n" + b"x" * 80, inline=True, mime="image/png")
    assert keep_attachment(tiny) is False
    winmail = InboundAttachment("winmail.dat", b"x" * 200)
    assert keep_attachment(winmail) is False
    pdf = InboundAttachment("policy.pdf", b"%PDF-1.4\n" + b"1" * 80)
    assert keep_attachment(pdf) is True


def test_shared_inbox_recipient_and_sender():
    inbox = "support@doxstation.com"
    assert is_shared_inbox_recipient("support@doxstation.com", inbox)
    assert is_shared_inbox_recipient("DocVault <support+bills@doxstation.com>", inbox)
    assert not is_shared_inbox_recipient("dvabc@in.docvault.doxstation.com", inbox)
    assert sender_email("Pravin <pravin@gmail.com>") == "pravin@gmail.com"
