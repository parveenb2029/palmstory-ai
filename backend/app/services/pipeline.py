"""The reading pipeline as a reusable unit: observation → interpretation →
reading → storyboard → comic. Emits stage callbacks so a job can report progress.
Provider-driven (mock by default). The image bytes stay in memory — never stored.
"""
from ..providers import get_image_provider, get_text_provider, get_vision_provider
from .comic import render_comic
from palmistry.interpretation import interpret

# (stage_name, progress%) checkpoints
STAGES = {
    "analyzing": 20,
    "interpreting": 40,
    "writing": 60,
    "storyboard": 75,
    "illustrating": 90,
    "done": 100,
}


def generate_reading(image_bytes: bytes, hand: str, quality: dict, detection: dict,
                     normalized_size: list, on_stage=None) -> dict:
    def stage(name: str):
        if on_stage:
            on_stage(name, STAGES.get(name, 0))

    vp = get_vision_provider()
    tp = get_text_provider()
    ip = get_image_provider()

    stage("analyzing")
    observation = vp.observe(image_bytes, hand)          # schema-validated
    stage("interpreting")
    interpretation = interpret(observation)              # deterministic, grounded
    stage("writing")
    reading = tp.write_reading(interpretation)           # narrated FROM interpretation
    stage("storyboard")
    storyboard = tp.storyboard(reading)                  # 4-beat arc
    stage("illustrating")
    comic = render_comic(storyboard, ip)                 # always renders (SVG fallback)
    stage("done")

    return {
        "hand": hand,
        "normalized_size": normalized_size,
        "quality": quality,
        "detection": detection,
        "observation": observation.model_dump(),
        "interpretation": interpretation.model_dump(),
        "reading": reading.model_dump(),
        "storyboard": storyboard.model_dump(),
        "comic": comic.model_dump(),
        "providers": {"vision": vp.name, "text": tp.name, "image": ip.name},
    }
