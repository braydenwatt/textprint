"""Provider interface. Implement `complete` and you can plug in any backend."""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def complete(self, system: str, prompt: str, temperature: float = 0.4,
                 max_tokens: int = 700) -> str:
        """Return the model's completion for (system, prompt) as plain text."""

    def check(self) -> str:
        """Optional health check; return a human-readable status string."""
        return "ok"
