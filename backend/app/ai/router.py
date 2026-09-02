"""Route classify/extract/reason operations to Gemini or local processors."""

from __future__ import annotations

import json

from app.ai.base import AIProvider
from app.ai.chat_intent import CHAT_INSTRUCTION, is_general_chat, local_chat_reply
from app.ai.gemini.provider import GeminiProvider
from app.config import get_settings
from app.documents.processing import classify_local, extract_fields, local_embedding
from app.logging import get_logger

log = get_logger("ai_router")
settings = get_settings()


class AIRouter:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self.provider = provider or GeminiProvider()

    def _use_external(self, external_allowed: bool) -> bool:
        return external_allowed and settings.gemini_configured

    async def classify(self, text: str, filename: str, *, external_allowed: bool) -> dict:
        local_type, category, sensitivity, confidence = classify_local(text, filename)
        result = {
            "document_type": local_type,
            "category": category,
            "sensitivity": sensitivity.value,
            "confidence": confidence,
            "provider": "local",
        }
        if not self._use_external(external_allowed):
            return result
        prompt = (
            "Classify this document from extracted text only. Return JSON with "
            "document_type, category, sensitivity (PUBLIC|PRIVATE|SENSITIVE|HIGHLY_SENSITIVE), confidence. "
            "If unsure, keep values conservative. Never invent identity numbers.\n"
            f"filename: {filename}\ntext: {text[:1500]}"
        )
        try:
            raw = await self.provider.generate(prompt, json_mode=True)
            parsed = json.loads(raw)
            result.update({k: parsed[k] for k in parsed if k in result})
            result["provider"] = self.provider.name
        except Exception:
            log.info("classify_fallback_local")
        return result

    async def extract(self, text: str, *, external_allowed: bool) -> list[dict]:
        fields = extract_fields(text)
        if not self._use_external(external_allowed):
            return fields
        prompt = (
            "Extract metadata as JSON list of {field,value,confidence,page}. "
            "Only include values explicitly present. Omit missing fields.\n"
            f"{text[:2000]}"
        )
        try:
            raw = await self.provider.generate(prompt, json_mode=True)
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            log.info("extract_fallback_local")
        return fields

    async def reason(self, context: dict, *, external_allowed: bool) -> str:
        if not self._use_external(external_allowed):
            return self._local_reason(context)
        prompt = json.dumps(context, default=str)
        try:
            return await self.provider.generate(prompt)
        except Exception:
            return self._local_reason(context)

    async def chat(self, question: str, *, language: str = "en", external_allowed: bool) -> str:
        fallback = local_chat_reply(question, language=language)
        if not self._use_external(external_allowed):
            return fallback
        prompt = f"{CHAT_INSTRUCTION}\nLanguage: {language}\nUser: {question}"
        try:
            reply = (await self.provider.generate(prompt)).strip()
            return reply or fallback
        except Exception:
            return fallback

    def _local_reason(self, context: dict) -> str:
        records = context.get("records") or []
        question = context.get("question") or ""
        lowered = question.lower()
        matched = context.get("matched_collections") or []
        folder_names = [col.get("name") for col in matched if col.get("name")]
        folder = ", ".join(folder_names)
        if not records and is_general_chat(question):
            return local_chat_reply(question, language=str(context.get("language") or "en"))
        if "expir" in lowered:
            lines = []
            for rec in records:
                if rec.get("expiry_date"):
                    lines.append(f"{rec['title']}: {rec['expiry_date']} (source: {rec['title']}, page 1)")
            if lines:
                return "Documents with expiry dates:\n" + "\n".join(lines)
            return "I couldn't find this information in your documents."
        if folder and not records:
            return f"I couldn't find any documents in {folder}."
        if records:
            lines = []
            for rec in records:
                names = [col.get("name") for col in rec.get("collections") or [] if col.get("name")]
                placed = f" in {', '.join(names)}" if names else ""
                lines.append(f"- {rec['title']}{placed}")
            heading = f"Documents in {folder}:" if folder else "Here are the matching documents:"
            return heading + "\n" + "\n".join(lines)
        return "I couldn't find this information in your documents."

    async def embed(self, texts: list[str], *, external_allowed: bool) -> list[list[float]]:
        if self._use_external(external_allowed):
            try:
                return await self.provider.embed(texts)
            except Exception:
                log.info("embed_fallback_local")
        return [local_embedding(text, settings.embedding_dimensions) for text in texts]


def get_router() -> AIRouter:
    return AIRouter()
