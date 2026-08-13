"""Mock providers — deterministic, offline, zero-cost. Used by default and in
all tests/CI so the full app is exercisable without spending AI credits."""
import hashlib

from ..schemas.ai import Observation, PalmObservation, Reading, Storyboard
from palmistry.schemas import Interpretation
from .base import ImageGenerationProvider, TextProvider, VisionProvider


# titles keyed by dominant theme → deterministic, still evocative
_TITLES = {
    "Freedom and choice": "The Map in Your Hand",
    "Connection": "The Open Heart",
    "Depth over speed": "The Long Road",
    "Vitality": "The Steady Flame",
    "Adventure": "The Wanderer's Palm",
    "Direction": "The North Star",
    "Creativity": "The Maker's Mark",
    "Expression": "The Bright Thread",
}


def _seed(data: bytes) -> int:
    return int(hashlib.sha256(data).hexdigest(), 16)


class MockVisionProvider(VisionProvider):
    name = "mock"

    def observe(self, image: bytes, hand: str) -> PalmObservation:
        # deterministic, but nudged by the image so different photos differ slightly
        bump = (_seed(image) % 7) / 100.0
        return PalmObservation(hand=hand, observations=[
            Observation(feature="heart_line", observation="clearly visible, curving upward", confidence=round(0.80 + bump, 2)),
            Observation(feature="head_line", observation="long and even", confidence=round(0.74 + bump, 2)),
            Observation(feature="life_line", observation="broad arc around the thumb", confidence=round(0.83 - bump, 2)),
            Observation(feature="fate_line", observation="faint / partial", confidence=round(0.31 + bump, 2)),
        ])


class MockTextProvider(TextProvider):
    name = "mock"

    def write_reading(self, interpretation: Interpretation) -> Reading:
        facets = {f.feature: f for f in interpretation.facets}
        themes = interpretation.themes
        strengths = interpretation.strengths
        challenges = interpretation.challenges

        def section(feature: str, fallback: str) -> str:
            f = facets.get(feature)
            if not f:
                return fallback
            text = f.interpretations[0]
            return text[0].upper() + text[1:] + "."

        title = _TITLES.get(themes[0], "The Story in Your Hand") if themes else "The Story in Your Hand"

        lead_strength = strengths[0].lower() if strengths else "a quiet resolve"
        lead_theme = themes[0].lower() if themes else "a story still forming"
        n_lines = sum(1 for f in interpretation.facets if f.detected)
        snapshot = (f"A {interpretation.hand} palm with {n_lines} clearly-read line"
                    f"{'' if n_lines == 1 else 's'}, where {lead_strength} meets {lead_theme}.")

        story_bits = []
        if strengths:
            story_bits.append("your palm speaks of " + ", ".join(s.lower() for s in strengths[:3]))
        if themes:
            story_bits.append("with threads of " + " and ".join(t.lower() for t in themes[:2]) + " running through it")
        story = ("In this entertainment-style reading, "
                 + ("; ".join(story_bits) if story_bits else "your palm keeps its own quiet counsel")
                 + ". The road ahead isn't drawn for you — that's the point.")

        return Reading(
            title=title,
            snapshot=snapshot,
            sections={
                "heart": section("heart_line", "A distinctive way of relating."),
                "mind": section("head_line", "A characteristic way of thinking."),
                "career": section("fate_line", "A path shaped by your own choices."),
            },
            strengths=strengths,
            challenges=challenges,
            themes=themes,
            story=story,
        )

    def storyboard(self, reading: Reading) -> Storyboard:
        from ..services.storyboard import compose
        return compose(reading)


class MockImageProvider(ImageGenerationProvider):
    name = "mock"

    def render_panel(self, panel, style) -> str:
        # the deterministic, offline SVG panel — always available
        from ..services.comic import svg_panel
        return svg_panel(panel, style)
