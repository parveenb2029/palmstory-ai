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
        # Vary the read per photo so different palms give different readings.
        # (Not a true palm read — that's what Gemini adds — but no longer identical for everyone.)
        import random
        rng = random.Random(_seed(image))
        heart = rng.choice([
            "clearly visible, curving upward",
            "straight and level",
            "long and deep",
            "short, kept close",
            "clear and strong",
        ])
        head = rng.choice([
            "long and even",
            "long, sloping gently downward",
            "short and straight",
            "deep and clear",
        ])
        life = rng.choice([
            "a broad, sweeping arc around the thumb",
            "deep and strong",
            "long and clear",
            "faint and narrow",
        ])
        fate = rng.choice([
            "clear and deep",
            "faint / partial",
            "absent",
            "wavy, wandering",
        ])
        obs = [
            Observation(feature="heart_line", observation=heart, confidence=round(rng.uniform(0.72, 0.9), 2)),
            Observation(feature="head_line", observation=head, confidence=round(rng.uniform(0.70, 0.88), 2)),
            Observation(feature="life_line", observation=life, confidence=round(rng.uniform(0.70, 0.90), 2)),
            Observation(feature="fate_line", observation=fate, confidence=round(rng.uniform(0.30, 0.80), 2)),
        ]
        if rng.random() > 0.45:   # a sun line appears on some hands
            obs.append(Observation(feature="sun_line",
                                   observation=rng.choice(["clear and present", "faint"]),
                                   confidence=round(rng.uniform(0.40, 0.80), 2)))
        return PalmObservation(hand=hand, observations=obs)


class MockTextProvider(TextProvider):
    name = "mock"

    def write_reading(self, interpretation: Interpretation) -> Reading:
        facets = {f.feature: f for f in interpretation.facets}
        themes = interpretation.themes
        strengths = interpretation.strengths
        challenges = interpretation.challenges

        def trait(feature: str):
            f = facets.get(feature)
            if not f or not f.interpretations:
                return None
            t = f.interpretations[0]
            for marker in (" read as ", " linked with ", " associated with ", " suggests "):
                if marker in t:
                    t = t.split(marker, 1)[1]
                    break
            # drop any KB caveat clause so it doesn't leak into the warm prose
            t = t.split("—")[0].split(" (")[0].split(", traditionally")[0]
            return t.strip().rstrip(".,;")

        title = _TITLES.get(themes[0], "The Story in Your Hand") if themes else "The Story in Your Hand"

        love_t = trait("heart_line")
        mind_t = trait("head_line")
        nat_t = trait("life_line")
        car_t = trait("fate_line") or trait("sun_line")

        snapshot = (f"Here's the little story your {interpretation.hand} hand seems to tell — "
                    "read it as a friendly mirror, not a map set in stone.")

        nature = ("At your core, you come across as "
                  + (nat_t or "steady, warm, and quietly your own person")
                  + ((f". People tend to feel your {strengths[0].lower()} before you even say a word.")
                     if strengths else "."))
        love = ("When it comes to love and closeness, you lean toward "
                + (love_t or "a warm, genuine way of connecting")
                + ". You tend to give people the real you — and that honesty is a quietly rare gift.")
        mind = ("The way your mind works is "
                + (mind_t or "thoughtful and distinctly your own")
                + ". You make sense of things in a way that's yours, and you trust it.")
        career = ("For drive and direction, your hand leans toward "
                  + (car_t or "a path you shape by your own choices")
                  + ". You're at your best when the work actually means something to you.")

        theme_line = ", ".join(t.lower() for t in themes[:3]) if themes else "finding your own quiet path"
        growth = (f" If there's a growing edge, it's {challenges[0].lower()} — nothing to fix, just something to keep an eye on."
                  if challenges else "")
        story = (f"If your palm had a headline, it would be about {theme_line}.{growth} "
                 "None of it is set in stone — the fun is simply noticing what's already yours, and leaning into it.")

        return Reading(
            title=title,
            snapshot=snapshot,
            sections={"nature": nature, "love": love, "mind": mind, "career": career},
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
