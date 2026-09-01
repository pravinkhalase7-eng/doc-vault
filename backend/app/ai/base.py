from abc import ABC, abstractmethod


class AIProvider(ABC):
    name = "base"
    external = False

    @abstractmethod
    async def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        raise NotImplementedError

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class FutureLocalProvider(AIProvider):
    """Placeholder for an on-device / VPS-local LLM."""

    name = "local"
    external = False

    async def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError
