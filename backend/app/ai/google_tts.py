"""Natural teacher speech for English practice (never vault text).

Prefers Gemini TTS (same Kore voice as AI Teacher), then Google Cloud Chirp 3 HD.
"""

from __future__ import annotations

import base64
import io
import wave

import httpx

from app.config import get_settings
from app.exceptions import AppError
from app.logging import get_logger

log = get_logger("tts")

CLOUD_TTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
TEACHER_VOICE = "Kore"
CHIRP_VOICES = (
    "en-IN-Chirp3-HD-Kore",
    "en-US-Chirp3-HD-Kore",
    "en-US-Chirp3-HD-Aoede",
    "en-US-Chirp3-HD-Leda",
)
GEMINI_TTS_MODELS = (
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
)


def pcm16_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    if pcm[:4] == b"RIFF":
        return pcm
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def google_tts_configured() -> bool:
    settings = get_settings()
    return bool(settings.gemini_api_key.strip() or settings.google_tts_api_key.strip())


def _teacher_prompt(text: str) -> str:
    return (
        "Speak like a warm, patient English teacher sitting next to the learner. "
        "Natural human pace, not a robot or GPS. Slight pause before the sentence they should repeat.\n\n"
        f"{text}"
    )


def _extract_gemini_audio(response) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline is None:
                continue
            data = getattr(inline, "data", None)
            if isinstance(data, bytes) and len(data) >= 64:
                return data
            if isinstance(data, str):
                raw = base64.b64decode(data)
                if len(raw) >= 64:
                    return raw
    raise RuntimeError("Gemini TTS returned no audio")


async def _synthesize_gemini(text: str, language: str) -> tuple[bytes, str] | None:
    settings = get_settings()
    api_key = settings.gemini_api_key.strip()
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    lang = (language or "en-IN").strip() or "en-IN"
    voice = (settings.gemini_tts_voice or TEACHER_VOICE).strip() or TEACHER_VOICE
    models = [settings.gemini_tts_model, *GEMINI_TTS_MODELS]
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            language_code=lang,
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            ),
        ),
    )
    spoken = _teacher_prompt(text)
    last_error = None
    for model in dict.fromkeys(m.strip() for m in models if m and m.strip()):
        try:
            response = client.models.generate_content(model=model, contents=spoken, config=config)
            audio = pcm16_to_wav(_extract_gemini_audio(response))
            log.info("tts_gemini", model=model, voice=voice, bytes=len(audio))
            return audio, "audio/wav"
        except Exception as exc:
            last_error = exc
            log.warning("tts_gemini_failed", model=model, error=type(exc).__name__)
    if last_error:
        log.warning("tts_gemini_exhausted", error=type(last_error).__name__)
    return None


async def _synthesize_chirp(text: str) -> tuple[bytes, str] | None:
    key = get_settings().google_tts_api_key.strip()
    if not key:
        return None
    last_error = "Cloud TTS returned no audio"
    encodings = (("LINEAR16", 24000), ("LINEAR16", None), ("MP3", None))
    async with httpx.AsyncClient(timeout=45.0) as client:
        for voice in CHIRP_VOICES:
            language_code = "-".join(voice.split("-")[:2])
            for encoding, sample_rate in encodings:
                audio_config: dict[str, object] = {
                    "audioEncoding": encoding,
                    "speakingRate": 0.98,
                }
                if sample_rate:
                    audio_config["sampleRateHertz"] = sample_rate
                try:
                    response = await client.post(
                        CLOUD_TTS_ENDPOINT,
                        params={"key": key},
                        json={
                            "input": {"text": text[:4500]},
                            "voice": {"languageCode": language_code, "name": voice},
                            "audioConfig": audio_config,
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
                raw = base64.b64decode(audio_b64)
                if len(raw) < 256:
                    continue
                if encoding == "LINEAR16":
                    audio, mime = pcm16_to_wav(raw, sample_rate or 24000), "audio/wav"
                else:
                    audio, mime = raw, "audio/mpeg"
                log.info("tts_chirp", voice=voice, encoding=encoding, bytes=len(audio))
                return audio, mime
    log.warning("tts_chirp_failed", error=last_error)
    return None


async def synthesize_speech(text: str, language: str = "en-IN") -> tuple[bytes, str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise AppError("TTS_EMPTY", "Nothing to speak", 400)
    gemini = await _synthesize_gemini(cleaned, language)
    if gemini:
        return gemini
    chirp = await _synthesize_chirp(cleaned)
    if chirp:
        return chirp
    raise AppError("TTS_UNAVAILABLE", "Natural teacher speech is not configured", 503)
