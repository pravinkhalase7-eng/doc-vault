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
    assert "better sentence" in lowered or "corrected" in lowered or "natural english" in lowered
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


def test_english_how_to_learn_gets_a_real_plan():
    reply, spoken = local_english_reply("how to learn english")
    lowered = reply.lower()
    assert "tell me a little more about what you want to know" not in lowered
    assert "good question" not in lowered
    assert "10 minutes" in lowered
    assert "sentence" in lowered
    assert "every day" in spoken.lower()
    want, _ = local_english_reply("I want to learn english")
    assert "10 minutes" in want.lower()
    improve, _ = local_english_reply("how can I improve my english?")
    assert "10 minutes" in improve.lower()


def test_english_fixes_went_tomorrow_and_spelling():
    corrected, notes = apply_english_fixes("i went to office tomorow")
    lowered = corrected.lower()
    assert "tomorrow" in lowered
    assert "tomorow" not in lowered
    assert "the office" in lowered
    assert "went" not in lowered
    assert "i'm going" in lowered or "i will go" in lowered
    assert any("future" in n.lower() or "went" in n.lower() for n in notes)
    reply, spoken = local_english_reply("i went to office tomorow")
    text = reply.lower()
    assert "i went to the office tomorow" not in text
    assert "i'm going to the office tomorrow" in text
    assert "tomorrow" in spoken.lower()
    past, past_notes = apply_english_fixes("i went to office yesterday")
    assert "i went to the office yesterday" in past.lower()
    assert "i'm going" not in past.lower()


def test_english_teaches_marathi_hunger():
    for msg in (
        "mala bhook lagali",
        "mala bhuk lagli",
        "mujhe bhookh lagi",
        "मला भूक लागली",
    ):
        reply, spoken = local_english_reply(msg)
        lowered = reply.lower()
        assert "that sounds natural" not in lowered, msg
        assert "feeling hungry" in lowered, msg
        assert "hungry" in spoken.lower(), msg
    reply, _ = local_english_reply("mala bhook lagali")
    assert "i am feeling hungry" in reply.lower()
    assert "i'm hungry" in reply.lower()


def test_english_teaches_marathi_school_holiday():
    reply, spoken = local_english_reply("mala udya school la sutti aahe")
    lowered = reply.lower()
    assert "mix in one english word" not in lowered
    assert "feeling hungry" not in lowered
    assert "tomorrow" in lowered
    assert "school" in lowered
    assert "holiday" in lowered or "don't have school" in lowered
    assert "i have a school holiday tomorrow" in lowered
    assert "tomorrow" in spoken.lower()
    today, _ = local_english_reply("mala school la sutti aahe")
    assert "hungry" not in today.lower()
    assert "school" in today.lower()


def test_english_teaches_marathi_shopping_today():
    reply, spoken = local_english_reply("mala aaj shopping la jaycha aahe")
    lowered = reply.lower()
    assert "it is today" not in lowered
    assert "that's today" not in lowered
    assert "shopping" in lowered
    assert "today" in lowered
    assert "have to go shopping" in lowered or "going shopping" in lowered
    assert "shopping" in spoken.lower()


def test_english_teaches_marathi_go_out_tomorrow():
    reply, spoken = local_english_reply("mala udya firayala jaycha")
    lowered = reply.lower()
    assert "go to firayala" not in lowered
    assert "have to go out tomorrow" in lowered
    assert "going out tomorrow" in lowered
    assert "go out" in spoken.lower()


def test_english_does_not_copy_unknown_marathi_as_a_place():
    reply, _ = local_english_reply("mala udya xyzayla jaycha")
    assert "to xyzayla" not in reply.lower()
    reply2, _ = local_english_reply("mala udya firayala jaycha")
    assert "to firayala" not in reply2.lower()


def test_pcm_wraps_as_wav():
    framed = pcm16_to_wav(b"\x00\x00" * 80)
    assert framed[:4] == b"RIFF"
    assert pcm16_to_wav(framed)[:4] == b"RIFF"
