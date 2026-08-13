"""Phase 7: deterministic, grounded interpretation from observations."""
from backend.app.schemas.ai import Observation, PalmObservation
from palmistry.interpretation import interpret
from palmistry.schemas import Interpretation


def _obs():
    return PalmObservation(hand="right", observations=[
        Observation(feature="heart_line", observation="clearly visible, curving upward", confidence=0.81),
        Observation(feature="head_line", observation="long and even", confidence=0.77),
        Observation(feature="life_line", observation="broad arc around the thumb", confidence=0.84),
        Observation(feature="fate_line", observation="faint / partial", confidence=0.31),
    ])


def test_interpretation_is_valid_and_covers_features():
    interp = interpret(_obs())
    assert isinstance(interp, Interpretation)
    assert [f.feature for f in interp.facets] == ["heart_line", "head_line", "life_line", "fate_line"]
    for f in interp.facets:
        assert f.interpretations  # never empty
        assert f.tradition and f.domain
    assert interp.summary and interp.disclaimer


def test_deterministic():
    assert interpret(_obs()) == interpret(_obs())


def test_grounded_mappings():
    interp = interpret(_obs())
    text = interp.summary.lower()
    # heart upward → warmth; fate faint → self-made / freedom
    assert "warm" in text
    fate = next(f for f in interp.facets if f.feature == "fate_line")
    assert fate.detected is False  # low confidence → not detected
    assert any("self-made" in s.lower() for s in fate.interpretations)
    assert "Freedom and choice" in interp.themes
    assert "Warmth in relationships" in interp.strengths


def test_no_lifespan_claims():
    # life line text must not claim length of life
    interp = interpret(_obs())
    life = next(f for f in interp.facets if f.feature == "life_line")
    joined = " ".join(life.interpretations).lower()
    assert "never" in joined  # explicitly disclaims lifespan
