"""Google Cloud Text-to-Speech for English practice (never vault text)."""

from __future__ import annotations

import base64

import httpx

from app.config import get_settings
from app.exceptions import AppError

TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"

_VOICES = {
    "en-IN": ("en-IN-Neural2-A", "en-IN-Wavenet-A", "en-IN-Standard-A"),
    "en-US": ("en-US-Neural2-C", "en-US-Wavenet-F", "en-US-Standard-C"),
    "en-GB": ("en-GB-Neural2-A", "en-GB-Wavenet-A", "en-GB-Standard-A"),
}


def google_tts_configured() -> bool:
    return bool(get_settings().google_tts_api_key.strip())


async def synthesize_speech(text: str, language: str = "en-IN") -> tuple[bytes, str]:
    key = get_settings().google_tts_api_key.strip()
    if not key:
        raise AppError("TTS_UNAVAILABLE", "Google text-to-speech is not configured", 503)
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise AppError("TTS_EMPTY", "Nothing to speak", 400)
    lang = (language or "en-IN").strip() or "en-IN"
    prefix = lang[:5]
    voices = _VOICES.get(prefix, _VOICES["en-IN"])
    last_error = "Google TTS returned no audio"
    async with httpx.AsyncClient(timeout=30.0) as client:
        for voice in voices:
            language_code = "-".join(voice.split("-")[:2])
            try:
                response = await client.post(
                    TTS_ENDPOINT,
                    params={"key": key},
                    json={
                        "input": {"text": cleaned[:4500]},
                        "voice": {"languageCode": language_code, "name": voice},
                        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.95},
                    },
                )
            except Exception as exc:
                last_error = str(exc)
                continue
            if response.status_code >= 400:
                last_error = (response.text or f"HTTP {response.status_code}")[:300]
                continue
            audio_b64 = str((response.json() or {}).get("audioContent") or "")
            if not audio_b64:
                continue
            audio = base64.b64decode(audio_b64)
            if len(audio) < 64:
                continue
            return audio, "audio/mpeg"
    raise AppError("TTS_FAILED", last_error, 502)
