"""Tests for Vedic astro advisor helpers."""

from datetime import date
from types import SimpleNamespace

from app.ai.astro import (
    ASTRO_SYSTEM_PROMPT,
    astrology_profile_from_user,
    build_astro_context,
    local_astro_reply,
    profile_complete_enough,
)


def _user(**prefs):
    preference = SimpleNamespace(
        birth_name=prefs.get("birth_name"),
        birth_date=prefs.get("birth_date"),
        birth_time=prefs.get("birth_time"),
        birth_place=prefs.get("birth_place"),
        language=SimpleNamespace(value="en"),
    )
    return SimpleNamespace(full_name="Pravin Khalase", preferences=preference)


def test_profile_without_birth_details():
    profile = astrology_profile_from_user(_user())
    assert profile["name"] == "Pravin Khalase"
    assert profile["has_birth_date"] is False
    assert profile["chart_data"] is None
    assert profile["chart_engine_available"] is False
    assert profile_complete_enough(profile) is False


def test_profile_with_dob_without_time():
    profile = astrology_profile_from_user(
        _user(birth_date=date(1990, 5, 15), birth_place="Pune", birth_name="Pravin")
    )
    assert profile["date_of_birth"] == "1990-05-15"
    assert profile["has_birth_date"] is True
    assert profile["has_birth_time"] is False
    assert profile["has_birth_place"] is True
    assert profile_complete_enough(profile) is True


def test_local_reply_never_invents_chart():
    profile = astrology_profile_from_user(_user(birth_date=date(1990, 5, 15)))
    reply = local_astro_reply("What does my career look like?", profile)
    lowered = reply.lower()
    assert "short answer" in lowered
    assert "invent" in lowered or "not invent" in lowered or "will not invent" in lowered
    assert "chart" in lowered
    # Must not fabricate specific planetary degrees / houses
    assert "mars in" not in lowered
    assert "lagna is" not in lowered


def test_local_reply_missing_dob():
    profile = astrology_profile_from_user(_user())
    reply = local_astro_reply("Tell me about my dasha", profile)
    assert "birth date" in reply.lower() or "won't invent" in reply.lower()


def test_system_prompt_forbids_invention():
    assert "NEVER invent" in ASTRO_SYSTEM_PROMPT
    ctx = build_astro_context(_user(birth_date=date(1990, 1, 1)), "hello", language="en")
    assert "ASTROLOGY PROFILE" in ctx
    assert "Do NOT invent" in ctx or "NEVER invent" in ctx
