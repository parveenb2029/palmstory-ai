"""Provider registry — selects providers from config, with a bounded fallback.

    VISION_PROVIDER   mock | gemini | huggingface   (default mock)
    TEXT_PROVIDER     mock | gemini | huggingface   (default mock)
    IMAGE_PROVIDER    mock | pollinations       (default mock)
    DEV_MOCK_AI       true → force mocks everywhere (default true)
    PROVIDER_FALLBACK_MOCK  true → real providers fall back to mock on error (default true)

Real providers are never selected in tests/CI because DEV_MOCK_AI defaults to
true; flip it (and set HF_TOKEN) to use them.
"""
import os

from .mock import MockImageProvider, MockTextProvider, MockVisionProvider
from .base import with_fallback


def _truthy(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _mocks_forced() -> bool:
    return _truthy("DEV_MOCK_AI", "true")


def _fallback_on() -> bool:
    return _truthy("PROVIDER_FALLBACK_MOCK", "true")


def _choice(env: str) -> str:
    if _mocks_forced():
        return "mock"
    return os.getenv(env, "mock").strip().lower()


def get_vision_provider():
    choice = _choice("VISION_PROVIDER")
    if choice == "gemini":
        from .gemini import GeminiVisionProvider
        real = GeminiVisionProvider()
        return with_fallback(real, MockVisionProvider()) if _fallback_on() else real
    if choice == "huggingface":
        from .hf import HFVisionProvider
        real = HFVisionProvider()
        return with_fallback(real, MockVisionProvider()) if _fallback_on() else real
    return MockVisionProvider()


def get_text_provider():
    choice = _choice("TEXT_PROVIDER")
    if choice == "gemini":
        from .gemini import GeminiTextProvider
        real = GeminiTextProvider()
        return with_fallback(real, MockTextProvider()) if _fallback_on() else real
    if choice == "huggingface":
        from .hf import HFTextProvider
        real = HFTextProvider()
        return with_fallback(real, MockTextProvider()) if _fallback_on() else real
    return MockTextProvider()


def get_image_provider():
    if _choice("IMAGE_PROVIDER") == "pollinations":
        from .hf import PollinationsImageProvider
        real = PollinationsImageProvider()
        return with_fallback(real, MockImageProvider()) if _fallback_on() else real
    return MockImageProvider()


def active_providers() -> dict:
    """Names of the currently-selected providers (for /healthz / observability)."""
    return {
        "vision": get_vision_provider().name,
        "text": get_text_provider().name,
        "image": get_image_provider().name,
        "mocks_forced": _mocks_forced(),
    }
