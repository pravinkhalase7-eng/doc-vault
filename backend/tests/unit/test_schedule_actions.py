from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai.schedule_actions import infer_title, parse_schedule_intent
from app.ai.vault_actions import parse_vault_intent
from app.utils.datetime_parse import parse_natural_datetime
from app.utils.phone import mask_phone, normalize_phone


def test_normalize_indian_mobile():
    assert normalize_phone("9876543210") == "+919876543210"
    assert normalize_phone("+91 98765 43210") == "+919876543210"
    assert normalize_phone("09876543210") == "+919876543210"
    assert normalize_phone("123") is None
    assert mask_phone("+919876543210").startswith("+91")
    assert "43210" not in mask_phone("+919876543210") or mask_phone("+919876543210").endswith("3210")


def test_parse_reminder_and_appointment_intents():
    remind = parse_schedule_intent("Remind me tomorrow at 10am to renew my passport")
    assert remind.kind == "reminder"
    assert "passport" in (remind.title or "").lower()
    appt = parse_schedule_intent("Doctor appointment Friday at 4pm, call me 1 hour before")
    assert appt.kind == "appointment"
    assert appt.title == "Doctor Appointment"
    assert parse_schedule_intent("list reminders").kind == "list"
    assert parse_schedule_intent("cancel that reminder").kind == "cancel_item"
    assert parse_schedule_intent("delete the passport file").kind == "none"


def test_delete_intent_still_wins_for_files():
    assert parse_vault_intent("delete the document Passport").kind == "delete_document"
    assert parse_schedule_intent("delete the document Passport").kind == "none"


def test_infer_title_from_call_phrase():
    assert infer_title("Remind me tomorrow at 12 PM to call Rahul") == "Call Rahul"


def test_parse_tomorrow_morning_ist():
    now = datetime(2026, 9, 3, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    parsed = parse_natural_datetime("Remind me tomorrow at 10am to renew my passport", now=now)
    assert parsed is not None
    assert parsed.ambiguous is False
    local = parsed.local_dt.astimezone(ZoneInfo("Asia/Kolkata"))
    assert local.day == 4
    assert local.hour == 10


def test_parse_relative_minutes():
    now = datetime(2026, 9, 3, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    parsed = parse_natural_datetime("remind me in 2 minutes to drink water", now=now)
    assert parsed is not None
    assert parsed.local_dt.minute == 2


def test_appointment_offset_minutes():
    now = datetime(2026, 9, 4, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    parsed = parse_natural_datetime("Doctor appointment Friday at 4pm, call me 1 hour before", now=now)
    assert parsed is not None
    assert parsed.offset_minutes == 60
    assert parsed.local_dt.hour == 16
