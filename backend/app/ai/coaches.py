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

ENGLISH_INSTRUCTION = """You are a friendly English speaking tutor (like a conversation coach).
Help the user learn English and correct their writing and speech.

Rules:
- Reply in simple, natural English.
- If they wrote something to correct, show:
  1) Corrected version
  2) What changed (short bullets)
  3) A line they can say out loud
- If they want to practice speaking, chat about the topic, then add a short "Corrections" section only when they made mistakes.
- Be encouraging. Do not mention DocVault, documents, or files unless they ask.
- Never invent document facts.
"""

PAVI_INSTRUCTION = """You are Pavi, a warm personal AI assistant.
Help with everyday questions, drafting messages, planning, explaining ideas, and light coaching.

Rules:
- Be concise, practical, and kind.
- If they want English practice or grammar correction, help briefly, then mention they can open English for daily speaking practice.
- If they ask about files, passports, PDFs, or their vault, tell them to use Ask My Vault. Do not invent document facts.
- Do not claim to have seen their documents.
"""

_FIXES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bi am agree\b", re.I), "I agree", "Say “I agree”, not “I am agree”."),
    (re.compile(r"\bdiscuss about\b", re.I), "discuss", "Use “discuss”, not “discuss about”."),
    (re.compile(r"\brevert back\b", re.I), "reply", "“Revert back” is office slang. Prefer “reply” or “get back to you”."),
    (re.compile(r"\breturn back\b", re.I), "return", "Drop “back” — “return” already means go back."),
    (re.compile(r"\bdo the needful\b", re.I), "please take care of this", "“Do the needful” sounds stiff. Try “please take care of this”."),
    (re.compile(r"\bprepone\b", re.I), "bring forward", "“Prepone” is Indian English. International English uses “bring forward” or “move earlier”."),
    (re.compile(r"\bi am having (\d+) years\b", re.I), r"I have \1 years", "Use “I have X years of experience”, not “I am having”."),
    (re.compile(r"\bgoing to market\b", re.I), "going to the market", "Add “the”: going to the market."),
    (re.compile(r"\bgoing to office\b", re.I), "going to the office", "Add “the”: going to the office."),
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


def title_for_mode(mode: str) -> str:
    return COACH_TITLES[mode]


def is_coach_title(title: str | None) -> bool:
    return (title or "") in COACH_TITLE_SET


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
    for pattern, repl, note in _FIXES:
        if pattern.search(corrected):
            corrected = pattern.sub(repl, corrected)
            if note not in notes:
                notes.append(note)
    polished = _polish(corrected)
    if polished != _polish(text or "") and "Start with a capital letter and end with a full stop." not in notes:
        if polished[0] != (text or "").lstrip()[:1]:
            notes.append("Start with a capital letter. The word “I” is always capital.")
    return polished, notes


def local_english_reply(message: str) -> str:
    text = (message or "").strip()
    lowered = text.lower()
    if not text or lowered in {"hi", "hello", "hey", "good morning", "good evening", "help"}:
        return (
            "Hi — I'm your English coach.\n\n"
            "Type or speak a sentence and I'll correct it. You can also say "
            "“let's practice a job interview” or paste a message you want to sound more natural.\n\n"
            "Turn on Cloud AI in Privacy Center for fuller conversation practice."
        )
    if any(word in lowered for word in ("interview", "practice", "speak", "conversation", "topic")):
        return (
            "Sure — let's practice.\n\n"
            "Tell me the situation (job interview, shop, office meeting) and I'll play the other person. "
            "After each line I'll correct any slips.\n\n"
            "You start: introduce yourself in one or two sentences."
        )
    corrected, notes = apply_english_fixes(text)
    if not notes and corrected.rstrip(".").lower() == _polish(text).rstrip(".").lower():
        return (
            "That looks clear.\n\n"
            f"Natural version:\n{corrected}\n\n"
            "Say it out loud once. If you want a more formal or more casual version, tell me."
        )
    bullets = "\n".join(f"- {note}" for note in notes) or "- Small polish for capitals and punctuation."
    return (
        f"Corrected:\n{corrected}\n\n"
        f"What to change:\n{bullets}\n\n"
        f"Try saying:\n“{corrected.rstrip('.')}.”"
    )


def local_pavi_reply(message: str) -> str:
    text = (message or "").strip()
    lowered = text.lower()
    if not text or lowered in {"hi", "hello", "hey", "good morning", "good evening", "who are you"}:
        return (
            "Hi, I'm Pavi.\n\n"
            "Ask me to draft a message, plan your day, explain something simply, or bounce an idea. "
            "For files in your vault, use Ask My Vault. For speaking practice, open English."
        )
    if any(word in lowered for word in ("correct", "grammar", "english", "sentence")):
        return local_english_reply(text) + "\n\nFor daily speaking practice, open English."
    if "plan" in lowered or "todo" in lowered or "to-do" in lowered or "schedule" in lowered:
        return (
            "Here's a simple plan from what you wrote:\n"
            f"1. {text[:180]}\n"
            "2. Pick the one thing that must happen today.\n"
            "3. Set a 25-minute block and do only that.\n"
            "4. Message me when you're done and we'll pick the next step.\n\n"
            "Turn on Cloud AI in Privacy Center if you want a fuller plan."
        )
    return (
        "I can help more when Cloud AI is on in Privacy Center.\n\n"
        "Meanwhile I can rewrite a short note, make a tiny plan, or send you to English for speaking practice.\n\n"
        f"You said: {text[:280]}"
    )


def local_coach_reply(mode: str, message: str) -> str:
    if mode == PAVI_MODE:
        return local_pavi_reply(message)
    return local_english_reply(message)


def _history_block(history: list[tuple[str, str]]) -> str:
    lines = []
    for role, content in history[-8:]:
        label = "User" if role == "user" else "Coach"
        lines.append(f"{label}: {content[:800]}")
    return "\n".join(lines)


async def generate_coach_reply(
    mode: str,
    message: str,
    *,
    history: list[tuple[str, str]] | None = None,
    external_allowed: bool = False,
) -> tuple[str, bool, str]:
    fallback = local_coach_reply(mode, message)
    if not (external_allowed and settings.gemini_configured):
        return fallback, False, "local"
    instruction = ENGLISH_INSTRUCTION if mode == ENGLISH_MODE else PAVI_INSTRUCTION
    prior = _history_block(history or [])
    prompt = f"{instruction}\n\n"
    if prior:
        prompt += f"{prior}\n"
    prompt += f"User: {message}"
    try:
        reply = (await GeminiProvider().generate(prompt)).strip()
        if reply:
            return reply, True, settings.gemini_model
    except Exception:
        pass
    return fallback, False, "local"
