from app.ai.base import AIProvider
from app.config import get_settings
from app.logging import get_logger

log = get_logger("gemini")
settings = get_settings()


class GeminiProvider(AIProvider):
    name = "gemini"
    external = True

    def __init__(self) -> None:
        self.model = settings.gemini_model
        self.embedding_model = settings.gemini_embedding_model

    async def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        try:
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key)
            config = {}
            if json_mode:
                config["response_mime_type"] = "application/json"
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config or None,
            )
            return (response.text or "").strip()
        except Exception as exc:
            log.warning("gemini_generate_failed", error=type(exc).__name__)
            raise

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        result = client.models.embed_content(model=self.embedding_model, contents=texts)
        embeddings = []
        for item in getattr(result, "embeddings", []) or []:
            embeddings.append(list(item.values))
        return embeddings
