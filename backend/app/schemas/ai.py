"""Structured contracts exchanged between AI providers and the pipeline.

These are enriched in later phases (observation → interpretation → reading →
storyboard → comic). Every provider returns one of these validated models —
never free prose where structure is required (spec §39).
"""
from pydantic import BaseModel, Field


class Observation(BaseModel):
    feature: str
    observation: str                       # what was SEEN (not interpreted)
    confidence: float = Field(ge=0, le=1)  # DETECTION confidence only


class PalmObservation(BaseModel):
    hand: str
    observations: list[Observation]


class Reading(BaseModel):
    title: str
    snapshot: str
    sections: dict[str, str] = {}
    strengths: list[str] = []
    challenges: list[str] = []
    themes: list[str] = []
    story: str = ""


class Panel(BaseModel):
    """One comic panel — enough structure to drive image generation (Phase 10)."""
    panel: int                       # 1-based index
    caption: str                     # text shown under the panel
    visual: str                      # detailed visual description (image-gen prompt body)
    beat: str = "scene"              # narrative beat: setup | rising | turn | resolution
    setting: str = ""                # where the scene takes place
    subject: str = ""                # who / what is in frame
    shot: str = ""                   # composition, e.g. "wide establishing shot"
    mood: str = ""                   # emotional tone


class StoryboardStyle(BaseModel):
    """Cross-panel visual grammar — keeps the comic coherent and on-brand."""
    art_style: str = "storybook comic, bold ink outlines, warm halftone shading"
    palette: str = "twilight indigo and warm gold"
    character: str = "a lone traveller with a small lantern"  # repeated for consistency
    aspect_ratio: str = "1:1"
    negative: str = "no text, no lettering, no watermark, no signature"


class Storyboard(BaseModel):
    title: str
    logline: str = ""                # one-line summary of the arc
    style: StoryboardStyle = Field(default_factory=StoryboardStyle)
    panels: list[Panel]


class ComicPanel(BaseModel):
    panel: int
    caption: str
    image_url: str        # data URL (SVG fallback) or remote URL (image model)
    source: str           # provider name, or "svg-fallback"


class Comic(BaseModel):
    title: str
    provider: str         # requested image provider
    panels: list[ComicPanel]
