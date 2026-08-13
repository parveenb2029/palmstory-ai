"""Real providers backed by the Hugging Face Inference router (OpenAI-compatible).

Config: HF_TOKEN (required), HF_VISION_MODEL, HF_TEXT_MODEL. Uses only the stdlib
(urllib) — no extra dependency. These raise ProviderError on any failure so the
registry's fallback can take over. Never used in tests/CI (mocks are default).
"""
import base64
import json
import os
import re
import urllib.request

from ..schemas.ai import Observation, PalmObservation, Panel, Reading, Storyboard  # noqa: F401
from palmistry.schemas import Interpretation
from .base import ImageGenerationProvider, ProviderError, TextProvider, VisionProvider

HF_URL = "https://router.huggingface.co/v1/chat/completions"
VISION_MODEL = os.getenv("HF_VISION_MODEL", "meta-llama/Llama-3.2-11B-Vision-Instruct")
TEXT_MODEL = os.getenv("HF_TEXT_MODEL", "meta-llama/Llama-3.2-11B-Vision-Instruct")


def _chat(messages, model, max_tokens=700, temperature=0.7):
    token = os.getenv("HF_TOKEN")
    if not token:
        raise ProviderError("HF_TOKEN is not set")
    payload = json.dumps({"model": model, "messages": messages,
                          "max_tokens": max_tokens, "temperature": temperature}).encode()
    req = urllib.request.Request(HF_URL, data=payload, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise ProviderError(f"Hugging Face request failed: {e}")


def _json_block(text: str):
    text = text.replace("```json", "").replace("```", "")
    m = re.search(r"[\[{].*[\]}]", text, re.DOTALL)
    if not m:
        raise ProviderError("model did not return JSON")
    return json.loads(m.group(0))


class HFVisionProvider(VisionProvider):
    name = "huggingface"

    def observe(self, image: bytes, hand: str) -> PalmObservation:
        b64 = base64.b64encode(image).decode()
        sys = ("You are a palm image analyst. Report ONLY what is visually present — never "
               "interpret meaning. Return JSON: {\"observations\":[{\"feature\":str,"
               "\"observation\":str,\"confidence\":0..1}]} for heart_line, head_line, "
               "life_line and fate_line. confidence = how clearly you SEE the line.")
        content = _chat([
            {"role": "system", "content": sys},
            {"role": "user", "content": [
                {"type": "text", "text": f"This is a {hand} palm."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]},
        ], VISION_MODEL, max_tokens=400)
        obj = _json_block(content)
        items = obj.get("observations", obj if isinstance(obj, list) else [])
        return PalmObservation(hand=hand, observations=[Observation(**o) for o in items])


class HFTextProvider(TextProvider):
    name = "huggingface"

    def write_reading(self, interpretation: Interpretation) -> Reading:
        sys = ("You are a warm palmistry storyteller. You are given a STRUCTURED, traditional "
               "interpretation of a palm. Write an ENTERTAINMENT reading grounded ONLY in what it "
               "provides — do not invent new claims, do not re-interpret the palm, and never make "
               "deterministic predictions or medical/financial/legal claims. Return JSON with keys: "
               "title, snapshot, sections{heart,mind,career}, strengths[], challenges[], themes[], story.")
        content = _chat([
            {"role": "system", "content": sys},
            {"role": "user", "content": interpretation.model_dump_json()},
        ], TEXT_MODEL)
        return Reading(**_json_block(content))

    def storyboard(self, reading: Reading) -> Storyboard:
        sys = (
            "Turn this palm reading into a 4-panel comic storyboard with a clear arc: "
            "setup, rising, turn, resolution. Keep ONE consistent character across all four "
            "panels (describe them the same way each time) and a recurring motif of a glowing "
            "palm whose lines become the world. The images must contain NO text. Return JSON: "
            '{"title":str,"logline":str,'
            '"style":{"art_style":str,"palette":str,"character":str,"aspect_ratio":"1:1",'
            '"negative":"no text, no lettering, no watermark"},'
            '"panels":[{"panel":int,"beat":str,"setting":str,"subject":str,"shot":str,'
            '"mood":str,"visual":str,"caption":str}]}'
        )
        content = _chat([
            {"role": "system", "content": sys},
            {"role": "user", "content": reading.model_dump_json()},
        ], TEXT_MODEL, max_tokens=700)
        return Storyboard(**_json_block(content))


class PollinationsImageProvider(ImageGenerationProvider):
    name = "pollinations"

    def render_panel(self, panel, style) -> str:
        # Build a per-panel prompt that repeats the consistent character + style so
        # panels stay visually coherent. The URL renders when the browser loads it —
        # no server-side network call, no API key.
        try:
            from urllib.parse import quote
            prompt = (f"{panel.visual}. {style.character}. {style.art_style}. "
                      f"{style.palette}. comic book panel. {style.negative}")
            return ("https://image.pollinations.ai/prompt/" + quote(prompt)
                    + "?width=768&height=768&nologo=true")
        except Exception as e:
            raise ProviderError(f"Pollinations render failed: {e}")
