"""English practice and Pavi — personal coaches that never read the vault."""

from __future__ import annotations

import re

from app.ai.gemini.provider import GeminiProvider
from app.config import get_settings

settings = get_settings()

ENGLISH_MODE = "english"
PAVI_MODE = "pavi"
COACH_MODES = (ENGLISH_MODE, PAVI_MODE)
COACH_TITLES = {ENGLISH_MODE: "English", PAVI_MODE: "Pavi"}
COACH_TITLE_SET = frozenset(COACH_TITLES.values())

ENGLISH_INSTRUCTION = """You are a warm, effective English tutor chatting with one adult learner (often an Indian English speaker). Talk like a real teacher on WhatsApp — human, specific, and useful. Never sound like a form, a bot, or a “tell me more” stall.

Always answer the actual message first. Then keep the conversation going with ONE related next step.

If they ask how to learn / improve / speak English: give a short real plan (daily speaking, real-life sentences, correction + repeat). Invite them to send one sentence from their day. Do not ask what they mean.

If they ask a question: answer it. Give examples. Then offer one practice line. Do not reply with only “Good question” or “tell me a little more”.

If they send a sentence to correct: show a fully natural version. Fix meaning, tense, spelling, and articles — never teach a sentence that is still wrong. Example: “I went … tomorrow” must become “I’m going … tomorrow” (or “I will go”). Then 1–3 short reasons and one line to say out loud.

If they are chatting: reply as a conversation partner, then lightly fix slips.

Never use canned closers: “what happened next”, “tell me one more sentence about this”, “your turn”, “tell me a little more about what you want to know”.
Only ask what happened next if they were clearly telling a story.
Do not mention DocVault, documents, or files unless they ask.

End with a single line in this exact form:
SPEAK: <one or two spoken sentences that actually answer them.>
"""

PAVI_INSTRUCTION = """You are Pavi, a warm personal AI assistant chatting like a helpful colleague.

Rules:
- Answer the actual request. Be concise, practical, and kind.
- Do not stall with “tell me more” until you have given a useful first answer or a draft they can use.
- If they want English practice or grammar correction, help briefly, then mention they can open English for daily speaking practice.
- If they ask about files, passports, PDFs, or their vault, tell them to use Ask My Vault. Do not invent document facts.
- Do not claim to have seen their documents.
"""

_SPELLINGS: list[tuple[str, str, str]] = [
    ("tomorow", "tomorrow", "Spelling: tomorrow (one m, two r’s)."),
    ("tommorow", "tomorrow", "Spelling: tomorrow (one m, two r’s)."),
    ("tommorrow", "tomorrow", "Spelling: tomorrow (one m, two r’s)."),
    ("tomarrow", "tomorrow", "Spelling: tomorrow (one m, two r’s)."),
    ("yestarday", "yesterday", "Spelling: yesterday."),
    ("yesterdy", "yesterday", "Spelling: yesterday."),
    ("todya", "today", "Spelling: today."),
    ("becaus", "because", "Spelling: because."),
    ("becouse", "because", "Spelling: because."),
    ("becuase", "because", "Spelling: because."),
    ("recieve", "receive", "Spelling: receive (i before e)."),
    ("seperate", "separate", "Spelling: separate."),
    ("definately", "definitely", "Spelling: definitely."),
    ("occured", "occurred", "Spelling: occurred (two r’s)."),
    ("enviroment", "environment", "Spelling: environment."),
    ("goverment", "government", "Spelling: government."),
    ("adress", "address", "Spelling: address (two d’s)."),
    ("buisness", "business", "Spelling: business."),
    ("sucess", "success", "Spelling: success (two c’s, two s’s)."),
    ("freind", "friend", "Spelling: friend."),
    ("thier", "their", "Spelling: their."),
    ("truely", "truly", "Spelling: truly (no e)."),
    ("begining", "beginning", "Spelling: beginning (two n’s)."),
    ("untill", "until", "Spelling: until (one l)."),
    ("teh", "the", "Spelling: the."),
    ("taht", "that", "Spelling: that."),
]

_FUTURE_TIME = re.compile(
    r"\b(?:tomorrow|tmrw|tmw|next\s+(?:week|month|year|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday))\b",
    re.I,
)
_PAST_TIME = re.compile(
    r"\b(?:yesterday|last\s+(?:week|month|year|night|monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday)|(?:a\s+|\d+\s+)days?\s+ago)\b",
    re.I,
)
_WENT_TO_GOING = [
    (re.compile(r"\bI went\b", re.I), "I'm going"),
    (re.compile(r"\bWe went\b", re.I), "We're going"),
    (re.compile(r"\bThey went\b", re.I), "They're going"),
    (re.compile(r"\bHe went\b", re.I), "He's going"),
    (re.compile(r"\bShe went\b", re.I), "She's going"),
    (re.compile(r"\bYou went\b", re.I), "You're going"),
]

_FIXES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bwill went\b", re.I), "will go", "After “will”, use go, not went."),
    (re.compile(r"\b(?:I am|I'm) go\b", re.I), "I'm going", "Say “I'm going”, not “I am go”."),
    (re.compile(r"\bI going\b", re.I), "I'm going", "Say “I'm going”, not “I going”."),
    (re.compile(r"\bdidn't went\b", re.I), "didn't go", "After didn’t, use go, not went."),
    (re.compile(r"\bi am agree\b", re.I), "I agree", "Say “I agree”, not “I am agree”."),
    (re.compile(r"\bdiscuss about\b", re.I), "discuss", "Use “discuss”, not “discuss about”."),
    (re.compile(r"\brevert back\b", re.I), "reply", "“Revert back” is office slang. Prefer “reply” or “get back to you”."),
    (re.compile(r"\breturn back\b", re.I), "return", "Drop “back” — “return” already means go back."),
    (re.compile(r"\bdo the needful\b", re.I), "please take care of this", "“Do the needful” sounds stiff. Try “please take care of this”."),
    (re.compile(r"\bprepone\b", re.I), "bring forward", "“Prepone” is Indian English. International English uses “bring forward” or “move earlier”."),
    (re.compile(r"\bi am having (\d+) years\b", re.I), r"I have \1 years", "Use “I have X years of experience”, not “I am having”."),
    (
        re.compile(r"\bi got to (?:the )?market\b", re.I),
        "I went to the market",
        "For a past trip, say “I went to the market”. Add “the” before market.",
    ),
    (re.compile(r"\bgot to (?:the )?market\b", re.I), "went to the market", "Say “went to the market”, not “got to market”."),
    (re.compile(r"\bgoing to market\b", re.I), "going to the market", "Add “the”: going to the market."),
    (re.compile(r"\bgoing to office\b", re.I), "going to the office", "Add “the”: going to the office."),
    (re.compile(r"\bgo to market\b", re.I), "go to the market", "Add “the”: go to the market."),
    (re.compile(r"\bgo to office\b", re.I), "go to the office", "Add “the”: go to the office."),
    (re.compile(r"\bto market\b(?!\s+a\b)", re.I), "to the market", "Add “the” before market."),
    (re.compile(r"\bat market\b", re.I), "at the market", "Add “the”: at the market."),
    (re.compile(r"\bto office\b", re.I), "to the office", "Add “the” before office."),
    (re.compile(r"\bgonna\b", re.I), "going to", "In writing, use “going to” instead of “gonna”."),
    (re.compile(r"\bwanna\b", re.I), "want to", "In writing, use “want to” instead of “wanna”."),
    (re.compile(r"\bdont\b", re.I), "don't", "Add the apostrophe: don't."),
    (re.compile(r"\bcant\b", re.I), "can't", "Add the apostrophe: can't."),
    (re.compile(r"\bwont\b", re.I), "won't", "Add the apostrophe: won't."),
    (re.compile(r"\bdidnt\b", re.I), "didn't", "Add the apostrophe: didn't."),
    (re.compile(r"\bisnt\b", re.I), "isn't", "Add the apostrophe: isn't."),
    (re.compile(r"\barent\b", re.I), "aren't", "Add the apostrophe: aren't."),
    (re.compile(r"\bwasnt\b", re.I), "wasn't", "Add the apostrophe: wasn't."),
    (re.compile(r"\bhavent\b", re.I), "haven't", "Add the apostrophe: haven't."),
    (re.compile(r"\bim\b", re.I), "I'm", "Write “I'm”."),
    (re.compile(r"\bu r\b", re.I), "you are", "Write “you are” instead of “u r”."),
    (re.compile(r"\bur\b", re.I), "your", "Write “your” instead of “ur”."),
    (re.compile(r"\bpls\b", re.I), "please", "Write “please” instead of “pls”."),
    (re.compile(r"\bthx\b", re.I), "thanks", "Write “thanks” instead of “thx”."),
]

_CORRECTION_ASK = re.compile(
    r"\b(correct|fix|check|improve)\b.{0,40}\b(english|grammar|sentence|this|it)\b"
    r"|\bis this correct\b|\bplease correct\b|\bcorrect this\b",
    re.I,
)
_STRIP_PREFIX = re.compile(
    r"^(?:please\s+)?(?:correct|fix|check|improve)\s+(?:this|my\s+english|my\s+sentence|the\s+sentence)[:.\-\s]+",
    re.I,
)
_STRIP_SUFFIX = re.compile(
    r"(?:,\s*)?(?:please\s+)?(?:correct|fix|check|improve)\s+(?:my\s+)?(?:english|this|it|grammar|the\s+sentence)(?:\s+please)?[.!]?\s*$",
    re.I,
)


def title_for_mode(mode: str) -> str:
    return COACH_TITLES[mode]


def is_coach_title(title: str | None) -> bool:
    return (title or "") in COACH_TITLE_SET


def extract_learner_text(message: str) -> tuple[str, bool]:
    text = (message or "").strip()
    asked = bool(_CORRECTION_ASK.search(text))
    cleaned = _STRIP_PREFIX.sub("", text)
    cleaned = _STRIP_SUFFIX.sub("", cleaned)
    cleaned = cleaned.strip(" ,.-")
    return (cleaned or text), asked


def _polish(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    cleaned = re.sub(r"\bi\b", "I", cleaned)
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def apply_english_fixes(text: str) -> tuple[str, list[str]]:
    corrected = (text or "").strip()
    notes: list[str] = []

    def add_note(note: str) -> None:
        if note and note not in notes:
            notes.append(note)

    for wrong, right, note in _SPELLINGS:
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.I)
        if pattern.search(corrected):
            corrected = pattern.sub(right, corrected)
            add_note(note)

    for _ in range(2):
        for pattern, repl, note in _FIXES:
            if pattern.search(corrected):
                corrected = pattern.sub(repl, corrected)
                add_note(note)

    if _FUTURE_TIME.search(corrected) and re.search(r"\bwent\b", corrected, re.I):
        for pattern, repl in _WENT_TO_GOING:
            if pattern.search(corrected):
                corrected = pattern.sub(repl, corrected)
        tense_note = (
            "Tomorrow is the future, so don’t use “went” (that’s past). Say “I'm going” or “I will go”."
        )
        if tense_note not in notes:
            notes.insert(0, tense_note)

    if _PAST_TIME.search(corrected):
        if re.search(r"\b(?:I'm|I am) going\b", corrected, re.I) and not _FUTURE_TIME.search(corrected):
            corrected = re.sub(r"\b(?:I'm|I am) going\b", "I went", corrected, flags=re.I)
            add_note("Yesterday is the past, so use “went”, not “I'm going”.")

    polished = _polish(corrected)
    original_polished = _polish(text or "")
    if polished != original_polished and len(notes) < 3:
        raw = (text or "").lstrip()
        if polished and raw and polished[0] != raw[:1]:
            add_note("Start with a capital letter. The word “I” is always capital.")
    return polished, notes[:3]


_QUESTION_START = re.compile(
    r"^(what|what's|whats|why|how|when|where|who|which|can|could|should|do|does|did|"
    r"is|are|am|will|would|may|have|has|had|tell me|explain|please tell)\b",
    re.I,
)


_LEARN_ENGLISH = re.compile(
    r"\b(?:how\s+(?:do\s+i|can\s+i|to)|i\s+want\s+to|want\s+to|help\s+me|teach\s+me|"
    r"ways?\s+to)\b.{0,50}\b(?:learn|improve|practi[cs]e|speak|study)\b.{0,30}\benglish\b"
    r"|\b(?:learn|improve|practi[cs]e|speak|study)\s+english\b",
    re.I,
)


def looks_like_question(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    if "?" in cleaned:
        return True
    if _LEARN_ENGLISH.search(cleaned):
        return True
    return bool(_QUESTION_START.match(cleaned))


def _learn_english_reply() -> tuple[str, str]:
    display = (
        "We can do this together — a little every day works better than a big course.\n\n"
        "A simple plan:\n"
        "1. Speak for 10 minutes a day. Short is fine.\n"
        "2. Use English from real life: market, office, family, messages.\n"
        "3. Send me one sentence. I’ll correct it and give you a natural line.\n"
        "4. Say that line out loud twice. Repeat useful sentences until they feel easy.\n\n"
        "Don’t try to learn everything. Start with what you need this week.\n\n"
        "Send me a sentence from today — work, shopping, or a message you want to write. "
        "I’ll reply like a teacher: correct it, explain why, and give you something to practise."
    )
    spoken = (
        "A good way to learn English is a little every day. "
        "Send me one sentence from your day, and I’ll help you say it more naturally."
    )
    return display, spoken


def spoken_english(corrected: str, notes: list[str]) -> str:
    line = (corrected or "").rstrip(".")
    why = notes[0] if notes else "Listen once, then say it with me."
    return (
        f"Nice try. A more natural way is: {line}. "
        f"{why} "
        f"Now say it with me: {line}."
    )


def _local_question_reply(learner: str, corrected: str, notes: list[str]) -> tuple[str, str]:
    lowered = learner.lower().strip().rstrip("?.! ")
    if _LEARN_ENGLISH.search(learner):
        return _learn_english_reply()
    if lowered in {"how are you", "how r you", "how are u"}:
        display = (
            "I'm doing well, thank you. How are you today?\n\n"
            "You can answer the same way:\n"
            "I'm good, thank you. How are you?"
        )
        spoken = "I'm doing well, thank you. You can say: I'm good, thank you. How are you?"
        return display, spoken
    if lowered in {"what is your name", "what's your name", "whats your name", "who are you"}:
        display = (
            "I'm your English coach. You can call me English.\n\n"
            "A natural question is:\nWhat's your name?\n\n"
            "You can answer: My name is …"
        )
        spoken = "I'm your English coach. A natural question is: What's your name?"
        return display, spoken
    if "difference between a and the" in lowered or re.search(r"\ba\s+and\s+the\b", lowered):
        display = (
            "Use “a” the first time you mention something, and “the” when we both know which one.\n\n"
            "I saw a dog. The dog was brown.\n"
            "I went to the market. (a specific, usual place)\n\n"
            "Try one: write a sentence with a, then a second sentence with the."
        )
        spoken = "Use a the first time. Use the when we both know which one. I went to the market."
        return display, spoken
    if re.search(r"\b(how do i say|how to say)\b", lowered):
        display = (
            "Happy to help you say it naturally.\n\n"
            "Type the idea in your own words — even mixed with Hindi is fine — "
            "and I’ll give you a simple English sentence to say out loud."
        )
        spoken = "Type the idea in your own words, and I’ll give you a simple English sentence to say."
        return display, spoken
    if re.search(r"\b(what is the meaning|what does .+ mean|meaning of)\b", lowered):
        display = (
            f"You asked: {corrected}\n\n"
            "Send the word or short phrase on its own, and I’ll explain it in simple English "
            "with one example you can say at work or at home."
        )
        spoken = "Send the word you want, and I’ll explain it in simple English with one example."
        return display, spoken
    polish = ""
    if notes:
        bullets = "\n".join(f"- {note}" for note in notes)
        polish = f"A natural way to ask this:\n{corrected}\n\nWhy:\n{bullets}\n\n"
    display = (
        f"{polish}"
        f"You asked: {corrected}\n\n"
        "Let’s use this like a real conversation. Tell me the situation in one line — "
        "work, shopping, travel, or a message you need to send — and I’ll give you the English to use, "
        "plus a line to practise out loud.\n\n"
        "Or send any sentence from today and I’ll help you say it more naturally."
    )
    spoken = (
        f"You can ask it like this: {corrected.rstrip('.')}. "
        "Tell me the situation — work, shopping, or a message — and I’ll give you the English to use."
        if notes
        else "Tell me the situation — work, shopping, or a message — and I’ll give you the English to use."
    )
    return display, spoken


def local_english_reply(message: str) -> tuple[str, str]:
    raw = (message or "").strip()
    learner, asked = extract_learner_text(raw)
    lowered = learner.lower()
    if not learner or lowered in {"hi", "hello", "hey", "good morning", "good evening", "help"}:
        display = (
            "Hi — I’m your English coach. Talk to me the way you would talk to a teacher.\n\n"
            "Ask anything, send a sentence from your day, or say “let’s practise a job interview”. "
            "I’ll answer, correct slips, and give you a line to say out loud."
        )
        spoken = "Hi. I’m your English coach. Ask me anything, or send a sentence from your day."
        return display, spoken
    if _LEARN_ENGLISH.search(learner):
        return _learn_english_reply()
    if looks_like_question(learner) and not asked:
        corrected, notes = apply_english_fixes(learner)
        return _local_question_reply(learner, corrected, notes)
    if any(word in lowered for word in ("interview", "practice", "conversation", "topic")) and not asked:
        display = (
            "Sure — let's practice.\n\n"
            "Tell me the situation (job interview, shop, office meeting) and I'll play the other person. "
            "After each line I'll correct any slips.\n\n"
            "You start: introduce yourself in one or two sentences."
        )
        spoken = "Let's practice. Tell me the situation, then introduce yourself in one or two sentences."
        return display, spoken
    corrected, notes = apply_english_fixes(learner)
    if notes or asked:
        bullets = "\n".join(f"- {note}" for note in notes) or "- I'll keep this natural and easy to say."
        display = (
            f"Almost — here's natural English:\n{corrected}\n\n"
            f"Why:\n{bullets}\n\n"
            f"Say this out loud:\n{corrected.rstrip('.')}."
        )
        return display, spoken_english(corrected, notes)
    display = (
        f"That sounds natural.\n\n"
        f"{corrected}\n\n"
        "Ask me anything, or give me another sentence to check."
    )
    spoken = f"That sounds natural: {corrected.rstrip('.')}. Ask me anything, or give me another sentence."
    return display, spoken


def local_pavi_reply(message: str) -> tuple[str, str]:
    text = (message or "").strip()
    lowered = text.lower()
    if not text or lowered in {"hi", "hello", "hey", "good morning", "good evening", "who are you"}:
        display = (
            "Hi, I'm Pavi.\n\n"
            "Ask me to draft a message, plan your day, explain something simply, or bounce an idea. "
            "For files in your vault, use Ask My Vault. For speaking practice, open English."
        )
        return display, "Hi, I'm Pavi. Tell me what you need help with."
    if any(word in lowered for word in ("correct", "grammar", "english", "sentence")):
        display, spoken = local_english_reply(text)
        return display + "\n\nFor daily speaking practice, open English.", spoken
    if "plan" in lowered or "todo" in lowered or "to-do" in lowered or "schedule" in lowered:
        display = (
            "Here's a simple plan from what you wrote:\n"
            f"1. {text[:180]}\n"
            "2. Pick the one thing that must happen today.\n"
            "3. Set a 25-minute block and do only that.\n"
            "4. Message me when you're done and we'll pick the next step."
        )
        return display, "Here's a simple plan. Pick the one thing that must happen today."
    display = (
        "I can help more when Cloud AI is on in Privacy Center.\n\n"
        "Meanwhile I can rewrite a short note, make a tiny plan, or send you to English for speaking practice.\n\n"
        f"You said: {text[:280]}"
    )
    return display, "I can rewrite a note, make a short plan, or send you to English for speaking practice."


def local_coach_reply(mode: str, message: str) -> tuple[str, str]:
    if mode == PAVI_MODE:
        return local_pavi_reply(message)
    return local_english_reply(message)


def _history_block(history: list[tuple[str, str]]) -> str:
    lines = []
    for role, content in history[-8:]:
        label = "User" if role == "user" else "Coach"
        lines.append(f"{label}: {content[:800]}")
    return "\n".join(lines)


def _split_spoken(reply: str, fallback: str) -> tuple[str, str]:
    match = re.search(r"\nSPEAK:\s*(.+)\s*$", reply.strip(), re.I | re.S)
    if not match:
        return reply.strip(), fallback
    spoken = " ".join(match.group(1).split())
    display = reply[: match.start()].strip()
    return display or reply.strip(), spoken or fallback


def _sentence_still_wrong(text: str) -> bool:
    lowered = (text or "").lower()
    if re.search(r"\b(?:tomorow|tommorow|tommorrow|tomarrow)\b", lowered):
        return True
    if _FUTURE_TIME.search(lowered) and re.search(r"\bwent\b", lowered):
        if not re.search(r"\b(?:i'm going|i am going|i will go|we're going|we will go)\b", lowered):
            return True
    return False


def _gemini_is_weak(reply: str, learner: str, *, asked: bool, question: bool) -> bool:
    lowered = (reply or "").lower()
    if "that looks clear" in lowered:
        return True
    if question and re.search(r"what happen(?:ed)? next", lowered):
        return True
    if question and (
        "tell me a little more about what you want to know" in lowered
        or "tell me a bit more and i'll explain" in lowered
        or "tell me a bit more and i’ll explain" in lowered
    ):
        return True
    if _sentence_still_wrong(reply):
        return True
    original = re.sub(r"\s+", " ", (learner or "").strip()).lower().rstrip(".")
    if asked and original and original in lowered and "went to the market" not in lowered:
        if "correct" in original or "got to market" in original:
            return True
    return False


async def generate_coach_reply(
    mode: str,
    message: str,
    *,
    history: list[tuple[str, str]] | None = None,
    external_allowed: bool = False,
) -> tuple[str, str, bool, str]:
    fallback, spoken = local_coach_reply(mode, message)
    if not (external_allowed and settings.gemini_configured):
        return fallback, spoken, False, "local"
    learner, asked = extract_learner_text(message)
    if _LEARN_ENGLISH.search(learner):
        asked = False
    instruction = ENGLISH_INSTRUCTION if mode == ENGLISH_MODE else PAVI_INSTRUCTION
    prior = _history_block(history or [])
    prompt = f"{instruction}\n\n"
    if prior:
        prompt += f"Recent chat:\n{prior}\n\n"
    question = looks_like_question(learner) and not asked
    if mode == ENGLISH_MODE:
        prompt += f"Learner message: {message}\n"
        if question:
            prompt += (
                "They asked a real question. Answer it like a human tutor: useful first, then one next step. "
                "If they asked how to learn English, give a short daily plan and invite one practice sentence. "
                "Do not stall. Do not say tell me more. Do not use a sentence-correction template. "
                "Never say what happened next.\n"
            )
            if _LEARN_ENGLISH.search(learner):
                prompt += f"A good local plan you may follow or improve:\n{fallback[:1200]}\n"
        else:
            prompt += (
                f"Sentence to teach (ignore ‘correct my english’ wording): {learner}\n"
                f"Local first pass (it may be incomplete — you must still fix remaining spelling, tense, and meaning):\n"
                f"{fallback[:1200]}\n"
                "Never copy a half-fixed sentence. Never teach “went” with “tomorrow”. "
                "Do not echo the uncorrected sentence as if it is already natural. "
                "Do not add “what happened next” unless they were telling a story.\n"
            )
        if asked:
            prompt += "They asked for a correction — you must teach, not praise the original line.\n"
    else:
        prompt += f"User: {message}\n"
    try:
        reply = (await GeminiProvider().generate(prompt)).strip()
        if reply:
            display, cloud_spoken = _split_spoken(reply, spoken)
            if mode == ENGLISH_MODE and _gemini_is_weak(
                display, learner, asked=asked, question=question
            ):
                return fallback, spoken, False, "local"
            return display, cloud_spoken, True, settings.gemini_model
    except Exception:
        pass
    return fallback, spoken, False, "local"
