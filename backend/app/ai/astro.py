"""Vedic astrology advisor chat — profile-aware, never invents chart data."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import get_router
from app.config import get_settings
from app.logging import get_logger
from app.models.ai import AIConversation, AIMessage
from app.models.enums import AIPrivacyMode
from app.models.user import User

log = get_logger("astro")
settings = get_settings()

ASTRO_CHANNEL = "astro"

ASTRO_SYSTEM_PROMPT = """
You are a personalized Vedic astrology consultant inside DocVault's Astro tab.

ROLE
- Use only the ASTROLOGY PROFILE and any calculated chart data provided in the system context.
- NEVER invent planetary positions, houses, nakshatras, dashas, degrees, lagna (ascendant),
  yoga combinations, or any other chart facts that are not explicitly present in the profile/context.
- If birth time is missing, acknowledge limits clearly: Lagna, house placements, and precise timing
  cannot be determined reliably. Still offer general, careful guidance based on birth date / Moon
  sign only when those are actually available — otherwise stay high-level and educational.
- If no chart engine data is present, say so. Do not fabricate a chart. You may discuss Vedic
  principles in general terms and relate them only to the birth details that exist.
- Prefer multi-factor interpretation. Never make single-factor predictions or speak in certainties.
  Use language like "may indicate", "often associated with", "worth watching".
- Respond in the user's language (match the language of their message).
- Tone: warm, calm, practical — not a generic newspaper horoscope, not fear-mongering.

RESPONSE STRUCTURE (use these section headings when giving a real reading)
1. Short Answer
2. Astrological Indicators (only cite indicators present in context; if none, say chart data is not available yet)
3. Interpretation
4. Guidance
5. Timing (only if relevant and supported by dasha/transit data in context; otherwise omit)

SENSITIVE TOPICS
- Health, finance, and relationships: careful, non-alarmist language; encourage professional advice
  where appropriate. No fatalistic declarations.
- Traditional remedies (mantra, dana, lifestyle) are optional and framed as cultural practices,
  never guarantees.

If the user greets you or asks what you can do, introduce yourself briefly and invite a question.
If birth details are missing, gently suggest saving DOB / place / time in the Astro profile once —
do not nag repeatedly.
""".strip()


def astrology_profile_from_user(user: User) -> dict:
    prefs = user.preferences
    if not prefs:
        return {
            "name": user.full_name,
            "date_of_birth": None,
            "birth_time": None,
            "birth_place": None,
            "has_birth_date": False,
            "has_birth_time": False,
            "has_birth_place": False,
            "chart_data": None,
            "chart_engine_available": False,
        }
    birth_date = prefs.birth_date
    birth_time = (prefs.birth_time or "").strip() or None
    birth_place = (prefs.birth_place or "").strip() or None
    birth_name = (prefs.birth_name or "").strip() or user.full_name
    return {
        "name": birth_name,
        "date_of_birth": birth_date.isoformat() if isinstance(birth_date, date) else None,
        "birth_time": birth_time,
        "birth_place": birth_place,
        "has_birth_date": birth_date is not None,
        "has_birth_time": bool(birth_time),
        "has_birth_place": bool(birth_place),
        # Reserved for a future Vedic chart engine — never invent values here.
        "chart_data": None,
        "chart_engine_available": False,
    }


def profile_complete_enough(profile: dict) -> bool:
    return bool(profile.get("has_birth_date"))


def build_astro_context(user: User, message: str, *, language: str) -> str:
    profile = astrology_profile_from_user(user)
    limits: list[str] = []
    if not profile["has_birth_date"]:
        limits.append("Birth date is missing — cannot personalize from natal chart factors.")
    if not profile["has_birth_time"]:
        limits.append(
            "Birth time is missing — Lagna, houses, and precise dasha timing cannot be determined."
        )
    if not profile["has_birth_place"]:
        limits.append("Birth place is missing — timezone/ayanamsha precision may be limited.")
    if not profile["chart_engine_available"] or not profile["chart_data"]:
        limits.append(
            "No calculated chart data is available yet (chart engine not wired). "
            "Do NOT invent planetary positions, houses, nakshatras, dashas, or degrees."
        )
    limits_block = "\n- ".join(limits)
    return (
        ASTRO_SYSTEM_PROMPT
        + "\n\nLanguage preference: "
        + language
        + "\nASTROLOGY PROFILE (JSON):\n"
        + str(profile)
        + "\n\nKNOWN LIMITS:\n- "
        + limits_block
        + "\n\nUser question:\n"
        + message
    )

def local_astro_reply(message: str, profile: dict, *, language: str = "en") -> str:
    name = profile.get("name") or "friend"
    has_dob = profile.get("has_birth_date")
    has_time = profile.get("has_birth_time")
    text = (message or "").strip().lower()

    if language and language.lower().startswith("hi"):
        if not has_dob:
            return (
                f"Namaste {name}. Main aapka Vedic astrology guide hoon.\n\n"
                "**Short Answer**\nAbhi birth date save nahi hai, isliye personal chart nahi bana sakta.\n\n"
                "**Guidance**\nAstro tab mein DOB (aur optional time/place) save karein — "
                "phir main aapke sawalon par dhyaan se jawab dunga. Chart data kabhi invent nahi karunga."
            )
        return (
            f"Namaste {name}.\n\n"
            "**Short Answer**\nAapka sawal mila. Abhi chart calculation engine connected nahi hai, "
            "isliye planetary positions / houses / dasha invent nahi karunga.\n\n"
            f"**Astrological Indicators**\nJanm tithi: {profile.get('date_of_birth') or '—'}"
            + (f"; samay: {profile.get('birth_time')}" if has_time else "; samay: uplabdh nahi")
            + (f"; sthan: {profile.get('birth_place')}" if profile.get("birth_place") else "")
            + ".\n\n"
            "**Interpretation**\nJab tak calculated chart nahi milta, sirf general Vedic guidance "
            "de sakta hoon — kisi grah/nakshatra ki jhoothi position nahi bataunga.\n\n"
            "**Guidance**\nApna sawal thoda specific rakhein (career, timing, relationship). "
            "Cloud AI on ho to main richer interpretation de sakta hoon, bina chart fake kiye."
        )

    greeting_tokens = ("hi", "hello", "hey", "namaste", "hiya")
    if text in greeting_tokens or (any(text.startswith(g) for g in greeting_tokens) and len(text) < 24):
        base = (
            f"Hi {name} — I'm your Vedic astrology guide in DocVault.\n\n"
            "**Short Answer**\nAsk about career, timing, relationships, or remedies, and I'll answer "
            "using your saved birth details — never inventing chart data.\n\n"
        )
        if not has_dob:
            return base + (
                "**Guidance**\nSave your date of birth (and optionally time & place) once in the "
                "Astro profile so answers can be personalized."
            )
        return base + (
            f"**Astrological Indicators**\nBirth date on file: {profile.get('date_of_birth')}. "
            + ("Birth time on file." if has_time else "Birth time not saved — Lagna/houses limited.")
            + "\n\n**Guidance**\nWhat would you like to explore?"
        )

    if not has_dob:
        return (
            f"**Short Answer**\nI can talk Vedic astrology with you, {name}, but I don't have your "
            "birth date yet — so I won't invent a chart.\n\n"
            "**Astrological Indicators**\nNone available until birth details are saved.\n\n"
            "**Interpretation**\nWithout DOB (and ideally birth time & place), natal placements, "
            "Lagna, and dashas cannot be assessed.\n\n"
            "**Guidance**\nSave your birth details once in the Astro profile, then ask again. "
            "I'll stay careful and multi-factor — never single-factor certainties."
        )

    limits = []
    if not has_time:
        limits.append("Birth time missing → Lagna, houses, and precise timing are unavailable.")
    limits.append("Chart engine not connected yet → planetary positions will not be fabricated.")

    return (
        f"**Short Answer**\nI heard your question. I can reflect on it with your saved birth details, "
        "but I will not invent planetary positions or dashas.\n\n"
        f"**Astrological Indicators**\nName: {name}; DOB: {profile.get('date_of_birth')}"
        + (f"; time: {profile.get('birth_time')}" if has_time else "; time: not provided")
        + (f"; place: {profile.get('birth_place')}" if profile.get("birth_place") else "")
        + ".\n"
        + "Calculated chart: not available yet.\n\n"
        "**Interpretation**\n"
        + " ".join(limits)
        + " When Cloud AI is enabled I can offer richer, careful Vedic framing; still only from "
        "real profile data.\n\n"
        "**Guidance**\nShare a specific life area (career move, relationship timing, health caution) "
        "and I'll structure Short Answer → Indicators → Interpretation → Guidance"
        + (" → Timing" if has_time else "")
        + " without false precision."
    )


async def run_astro_agent(
    db: AsyncSession,
    user: User,
    message: str,
    *,
    conversation_id: str | None = None,
    language: str | None = None,
) -> dict:
    prefs = user.preferences
    lang = language or (prefs.language.value if prefs else "en")
    external = bool(prefs and prefs.external_ai_enabled and prefs.ai_privacy_mode != AIPrivacyMode.PRIVATE)
    profile = astrology_profile_from_user(user)

    conversation = None
    if conversation_id:
        conversation = await db.get(AIConversation, conversation_id)
        if conversation and (
            conversation.user_id != user.id
            or getattr(conversation, "channel", "vault") != ASTRO_CHANNEL
        ):
            conversation = None
    if not conversation:
        conversation = AIConversation(
            user_id=user.id,
            title=(message[:80] or "Astro"),
            language=lang,
            channel=ASTRO_CHANNEL,
        )
        db.add(conversation)
        await db.flush()

    answer: str
    model = "local"
    used_external = False
    if external and settings.gemini_configured:
        prompt = build_astro_context(user, message, language=lang)
        try:
            router = get_router()
            reply = (await router.provider.generate(prompt)).strip()
            if reply:
                answer = reply
                model = settings.gemini_model
                used_external = True
            else:
                answer = local_astro_reply(message, profile, language=lang)
        except Exception:
            log.info("astro_gemini_fallback_local")
            answer = local_astro_reply(message, profile, language=lang)
    else:
        answer = local_astro_reply(message, profile, language=lang)

    db.add(
        AIMessage(
            conversation_id=conversation.id,
            role="user",
            content=message,
            data_access={
                "channel": ASTRO_CHANNEL,
                "astrology_profile": {
                    "has_birth_date": profile["has_birth_date"],
                    "has_birth_time": profile["has_birth_time"],
                    "has_birth_place": profile["has_birth_place"],
                    "chart_engine_available": False,
                },
            },
        )
    )
    data_access = {
        "channel": ASTRO_CHANNEL,
        "used": ["astrology_profile"],
        "raw_document": False,
        "external_ai": used_external,
        "model": model,
        "documents": [],
        "blocked": [],
        "astrology_profile": {
            "has_birth_date": profile["has_birth_date"],
            "has_birth_time": profile["has_birth_time"],
            "has_birth_place": profile["has_birth_place"],
            "chart_engine_available": False,
        },
    }
    assistant = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        evidence=[],
        model=model,
        external_ai=used_external,
        data_access=data_access,
    )
    db.add(assistant)
    await db.commit()

    return {
        "conversation_id": conversation.id,
        "message_id": assistant.id,
        "answer": answer,
        "evidence": [],
        "data_access": data_access,
        "external_ai": used_external,
        "model": model,
        "astrology_profile": profile,
    }
