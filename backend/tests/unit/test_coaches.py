from app.ai.coaches import (
    apply_english_fixes,
    extract_learner_text,
    is_coach_title,
    local_english_reply,
    local_pavi_reply,
    title_for_mode,
)
from app.ai.google_tts import pcm16_to_wav


def test_coach_titles():
    assert title_for_mode("english") == "English"
    assert title_for_mode("pavi") == "Pavi"
    assert is_coach_title("English")
    assert is_coach_title("Pavi")
    assert not is_coach_title("Ask My Vault")


def test_english_corrects_common_slips():
    corrected, notes = apply_english_fixes("i am going to market and i dont agree")
    assert "going to the market" in corrected.lower()
    assert "don't" in corrected.lower()
    assert notes


def test_english_greeting_does_not_search_vault():
    reply, spoken = local_english_reply("hello")
    assert "couldn't find" not in reply.lower()
    assert "english" in reply.lower()
    assert spoken


def test_english_correction_reply_has_sections():
    reply, spoken = local_english_reply("pls revert back after you discuss about it")
    lowered = reply.lower()
    assert "better sentence" in lowered or "corrected" in lowered
    assert "discuss" in lowered
    assert "please" in lowered
    assert "say it with me" in spoken.lower() or "went to the market" in spoken.lower()


def test_english_teaches_got_to_market():
    sentence, asked = extract_learner_text("I got to market, correct my english")
    assert asked
    assert sentence.lower() == "i got to market"
    reply, spoken = local_english_reply("I got to market, correct my english")
    lowered = reply.lower()
    assert "that looks clear" not in lowered
    assert "went to the market" in lowered
    assert "the market" in spoken.lower()


def test_pavi_intro_and_vault_handoff():
    reply, spoken = local_pavi_reply("hi")
    assert "pavi" in reply.lower()
    assert "ask my vault" in reply.lower()
    assert "pavi" in spoken.lower()


def test_english_question_does_not_ask_what_happened_next():
    reply, spoken = local_english_reply("how are you")
    assert "happened next" not in reply.lower()
    assert "happened next" not in spoken.lower()
    assert "doing well" in reply.lower()
    follow, follow_spoken = local_english_reply("I went to the market")
    assert "happened next" not in follow.lower()
    assert "happened next" not in follow_spoken.lower()


def test_pcm_wraps_as_wav():
    framed = pcm16_to_wav(b"\x00\x00" * 80)
    assert framed[:4] == b"RIFF"
    assert pcm16_to_wav(framed)[:4] == b"RIFF"
