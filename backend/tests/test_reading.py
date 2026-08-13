"""Phase 8: narrative reading generated FROM the grounded interpretation."""
from backend.app.providers.mock import MockTextProvider
from backend.app.schemas.ai import Observation, PalmObservation, Reading
from palmistry.interpretation import interpret


def _interp():
    obs = PalmObservation(hand="right", observations=[
        Observation(feature="heart_line", observation="clearly visible, curving upward", confidence=0.81),
        Observation(feature="head_line", observation="long and even", confidence=0.77),
        Observation(feature="life_line", observation="broad arc around the thumb", confidence=0.84),
        Observation(feature="fate_line", observation="faint / partial", confidence=0.31),
    ])
    return interpret(obs)


def test_reading_is_valid_and_grounded():
    r = MockTextProvider().write_reading(_interp())
    assert isinstance(r, Reading)
    assert r.title and r.snapshot and r.story
    assert set(r.sections) == {"heart", "mind", "career"}
    # grounded: strengths/themes come straight from the interpretation
    interp = _interp()
    assert r.strengths == interp.strengths
    assert r.themes == interp.themes
    # the heart section reflects the heart-line interpretation (warmth)
    assert "warm" in r.sections["heart"].lower()


def test_reading_is_deterministic():
    assert MockTextProvider().write_reading(_interp()) == MockTextProvider().write_reading(_interp())


def test_title_follows_dominant_theme():
    r = MockTextProvider().write_reading(_interp())
    # dominant theme for this palm is "Connection" (heart upward is first facet)
    assert r.title in {"The Open Heart", "The Story in Your Hand"}
    assert isinstance(r.title, str) and len(r.title) > 3


def test_no_prediction_language_in_story():
    r = MockTextProvider().write_reading(_interp())
    lowered = r.story.lower()
    for banned in ["will die", "you will", "guaranteed", "diagnos"]:
        assert banned not in lowered
