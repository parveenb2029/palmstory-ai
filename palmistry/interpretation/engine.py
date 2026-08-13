"""Interpretation engine.

Maps a PalmObservation to a structured Interpretation using the traditional
knowledge base — deterministically (same input → same output), never random and
never invented. The LLM (Phase 8) writes the narrative FROM this, so meaning is
grounded and auditable.
"""
import json
from pathlib import Path

from backend.app.schemas.ai import PalmObservation
from palmistry.schemas.interpretation import Facet, Interpretation

_KB_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "lines.json"
with _KB_PATH.open(encoding="utf-8") as _f:
    KB = json.load(_f)

DETECT_THRESHOLD = 0.5


def _add(seq: list, value: str) -> None:
    if value and value not in seq:
        seq.append(value)


def interpret(observation: PalmObservation) -> Interpretation:
    facets: list[Facet] = []
    strengths: list[str] = []
    challenges: list[str] = []
    themes: list[str] = []

    for obs in observation.observations:
        node = KB.get(obs.feature)
        if not node:
            continue
        faint = obs.confidence < DETECT_THRESHOLD
        text = obs.observation.lower() + (" faint" if faint else "")

        interps: list[str] = []
        for rule in node["qualities"]:
            if any(kw in text for kw in rule["match"]):
                interps.append(rule["text"])
                _add(strengths, rule.get("strength"))
                _add(challenges, rule.get("challenge"))
                _add(themes, rule.get("theme"))
        if not interps:
            interps.append(node["default"]["text"])

        facets.append(Facet(
            feature=obs.feature,
            tradition=node["tradition"],
            domain=node["domain"],
            detected=not faint,
            detection_confidence=obs.confidence,
            interpretations=interps,
        ))

    summary = "; ".join(
        f"{f.tradition.split(' (')[0]} — {f.interpretations[0]}" for f in facets
    ) or "A palm with a quiet, still-forming story."

    return Interpretation(
        hand=observation.hand,
        facets=facets,
        strengths=strengths,
        challenges=challenges,
        themes=themes,
        summary=summary,
    )
