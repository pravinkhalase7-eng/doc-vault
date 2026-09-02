"""Greetings and general questions should not be treated as vault searches."""

from __future__ import annotations

import re

GREETING_RE = re.compile(
    r"^(hi+|hii+|hello+|helo+|hey+|yo|hiya|howdy|namaste|namaskar|hola)"
    r"(?:\s+(there|docvault|vault|pavi))?"
    r"[\s!.?,]*$",
    re.I,
)
TIME_GREETING_RE = re.compile(
    r"^good\s+(morning|afternoon|evening|night)(?:\s+(there|docvault|vault))?[\s!.?,]*$",
    re.I,
)
SMALLTALK_RE = re.compile(
    r"^(how\s+are\s+you(?:\s+doing)?|how'?s\s+it\s+going|what'?s\s+up|whats\s+up|"
    r"how\s+is\s+it\s+going|sup)[\s!.?,]*$",
    re.I,
)
THANKS_RE = re.compile(r"^(thanks|thank\s+you|thx|ty|thankyou)[\s!.?,]*$", re.I)
HELP_RE = re.compile(
    r"\b(what can you do|what do you do|how (?:do|does|can) (?:you|this|i)|"
    r"help(?:\s+me)?|who are you|what are you|what is (?:this|docvault)|"
    r"your capabilities)\b",
    re.I,
)
VAULT_RE = re.compile(
    r"\b(document|documents|file|files|folder|folders|collection|collections|vault|"
    r"passport|visa|aadhaar|aadhar|pan|license|licence|insurance|policy|"
    r"expiry|expire|expiring|upload|delete|remove|remind|reminder|appointment|"
    r"call me|phone call)\b",
    re.I,
)
SEARCH_RE = re.compile(
    r"\b(show|find|list|search|where is|when does|when is|which documents?)\b",
    re.I,
)


def _clean(message: str) -> str:
    return re.sub(r"\s+", " ", (message or "").strip())


def is_greeting(message: str) -> bool:
    text = _clean(message)
    if not text:
        return False
    if GREETING_RE.match(text) or TIME_GREETING_RE.match(text) or SMALLTALK_RE.match(text):
        return True
    if re.match(r"^(hi+|hello+|hey+|namaste|namaskar)\b", text, re.I) and not looks_like_vault_question(text):
        return True
    return False


def is_thanks(message: str) -> bool:
    return bool(THANKS_RE.match(_clean(message)))


def is_help(message: str) -> bool:
    return bool(HELP_RE.search(_clean(message)))


def looks_like_vault_question(message: str) -> bool:
    text = _clean(message)
    return bool(VAULT_RE.search(text) or SEARCH_RE.search(text))


def is_general_chat(message: str) -> bool:
    """True when the message is a greeting or not about vault files."""
    if is_greeting(message) or is_thanks(message):
        return True
    if looks_like_vault_question(message):
        return False
    return True


CHAT_INSTRUCTION = (
    "You are DocVault, a friendly personal assistant for a private document vault. "
    "If the user greets you, greet them back and briefly say you can find files, "
    "set reminders, and answer questions. Answer their current question helpfully. "
    "Do not invent facts about files in their vault. If they ask about a specific "
    "document, say you can look it up in the vault. Keep replies concise. "
    "Respond in the user's language."
)


def local_chat_reply(message: str, *, language: str = "en") -> str:
    if is_greeting(message):
        if SMALLTALK_RE.match(_clean(message)):
            return (
                "I'm doing well — thanks for asking. I'm DocVault. I can find files "
                "in your vault, set reminders and calls, and answer questions. What do you need?"
            )
        return (
            "Hi — I'm DocVault. I can find files in your vault, set reminders and calls, "
            "and answer questions. What would you like to do?"
        )
    if is_thanks(message):
        return "You're welcome. Ask whenever you need something from the vault."
    if is_help(message):
        return (
            "I can help you:\n"
            "• Find files and collections in your vault\n"
            "• Check expiry dates\n"
            "• Set reminders and call you at a time you choose\n"
            "• Answer questions — turn on Cloud AI in Settings for general topics\n\n"
            "Try “show me all collections” or “remind me tomorrow at 10am to renew my passport”."
        )
    if language and language.lower().startswith("hi"):
        return (
            "Main yahan hoon. Vault ke files, reminders, aur sawalon mein madad kar sakta hoon. "
            "Kya dekhna hai?"
        )
    return (
        "I'm here. Ask me about a file in your vault, set a reminder, "
        "or turn on Cloud AI in Settings if you want general answers."
    )
