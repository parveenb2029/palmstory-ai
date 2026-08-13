"""Structured interpretation — the auditable bridge between raw observations and
the LLM narrative (Phase 8). Deterministic, grounded in the knowledge base."""
from pydantic import BaseModel


class Facet(BaseModel):
    feature: str
    tradition: str                 # e.g. "Hridaya Rekha (heart line)"
    domain: str                    # e.g. "emotions and relationships"
    detected: bool                 # False when the line was faint / low-confidence
    detection_confidence: float
    interpretations: list[str]     # traditional "is read as ..." statements


class Interpretation(BaseModel):
    hand: str
    facets: list[Facet]
    strengths: list[str]
    challenges: list[str]
    themes: list[str]
    summary: str                   # deterministic synthesis (NOT the narrative)
    disclaimer: str = ("Traditional palmistry interpretation, offered for "
                       "entertainment — not prediction or advice.")
