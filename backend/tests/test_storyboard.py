"""Phase 9: reading → coherent, deterministic 4-beat storyboard."""
from backend.app.providers.mock import MockTextProvider, MockVisionProvider
from backend.app.services.storyboard import compose
from backend.app.schemas.ai import Reading, Storyboard
from palmistry.interpretation import interpret


def _reading(themes=None, strengths=None):
    return Reading(
        title="The Open Heart",
        snapshot="snap",
        sections={"heart": "h", "mind": "m", "career": "c"},
        strengths=strengths or ["Warmth in relationships", "Resilience"],
        challenges=["Letting others in"],
        themes=themes or ["Connection", "Vitality"],
        story="a story",
    )


def test_four_beat_arc_and_schema():
    b = compose(_reading())
    assert isinstance(b, Storyboard) and len(b.panels) == 4
    assert [p.beat for p in b.panels] == ["setup", "rising", "turn", "resolution"]
    for i, p in enumerate(b.panels, start=1):
        assert p.panel == i
        assert p.visual and p.caption and p.shot and p.setting  # image-gen ready
    assert b.title == "The Open Heart" and b.logline


def test_consistent_character_across_panels():
    b = compose(_reading())
    char = b.style.character
    assert char and all(char in p.visual for p in b.panels)  # same protagonist every panel


def test_palette_and_metaphor_follow_theme():
    warm = compose(_reading(themes=["Connection"]))
    free = compose(_reading(themes=["Freedom and choice"]))
    assert warm.style.palette != free.style.palette          # theme changes palette
    assert "rose" in warm.style.palette
    # dominant theme surfaces in the rising panel's caption
    assert "connection" in warm.panels[1].caption.lower()


def test_deterministic():
    assert compose(_reading()) == compose(_reading())


def test_no_text_in_images_directive():
    b = compose(_reading())
    assert "no text" in b.style.negative.lower()


def test_unknown_theme_falls_back_gracefully():
    b = compose(_reading(themes=[]))  # no themes → default palette/metaphor, still 4 panels
    assert len(b.panels) == 4 and b.style.palette


def test_end_to_end_from_observation():
    reading = MockTextProvider().write_reading(interpret(MockVisionProvider().observe(b"x", "right")))
    b = MockTextProvider().storyboard(reading)
    assert len(b.panels) == 4 and b.style.character
