"""LLM provider adapters. All expose the same `.complete(system, prompt) -> str`.

Default is local Ollama (no data leaves the machine, no API keys). Cloud
adapters can be added behind the same interface; the pipeline never assumes one.
"""
from .base import LLMProvider
from .ollama import OllamaProvider


def get_provider(name, **kw):
    name = (name or "ollama").lower()
    if name == "ollama":
        return OllamaProvider(**kw)
    raise ValueError(f"unknown provider '{name}'. built-in: ollama "
                     "(add cloud adapters in textprint/providers/)")


__all__ = ["LLMProvider", "OllamaProvider", "get_provider"]
