"""AI provider interfaces.

Three swappable capabilities — vision, text, image generation — each an abstract
base with a `name`. Concrete providers live alongside (mock.py, hf.py,
pollinations.py) and are chosen by config in registry.py. `with_fallback` gives a
single, bounded fallback (no retry loops) per spec §38.
"""
from abc import ABC, abstractmethod

from ..schemas.ai import PalmObservation, Panel, Reading, Storyboard, StoryboardStyle
from palmistry.schemas import Interpretation


class ProviderError(Exception):
    """Raised by a provider on failure (quota, network, bad output, no creds)."""


class VisionProvider(ABC):
    name: str = "base"

    @abstractmethod
    def observe(self, image: bytes, hand: str) -> PalmObservation:
        """Look at a palm image and return structured, schema-valid observations."""


class TextProvider(ABC):
    name: str = "base"

    @abstractmethod
    def write_reading(self, interpretation: Interpretation) -> Reading:
        """Turn the structured, grounded Interpretation (Phase 7) into an
        entertaining, structured reading. The narrative is written FROM the
        interpretation — the model doesn't re-interpret the palm itself."""

    @abstractmethod
    def storyboard(self, reading: Reading) -> Storyboard:
        """Turn a reading into a validated comic storyboard."""


class ImageGenerationProvider(ABC):
    name: str = "base"

    @abstractmethod
    def render_panel(self, panel: Panel, style: StoryboardStyle) -> str:
        """Render one comic panel and return its image URL (data or remote).
        May raise ProviderError; the comic service then uses the SVG fallback."""


class _FallbackProxy:
    """Calls the primary provider; on ANY error, calls the fallback once."""

    def __init__(self, primary, fallback):
        self._p = primary
        self._f = fallback
        self.name = f"{primary.name}->{fallback.name}"

    def __getattr__(self, attr):
        primary_attr = getattr(self._p, attr)
        if not callable(primary_attr):
            return primary_attr
        fallback_attr = getattr(self._f, attr)

        def wrapper(*args, **kwargs):
            try:
                return primary_attr(*args, **kwargs)
            except Exception:
                return fallback_attr(*args, **kwargs)
        return wrapper


def with_fallback(primary, fallback):
    return _FallbackProxy(primary, fallback)
