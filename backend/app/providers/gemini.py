"""Google Gemini providers — real, image-grounded palm readings on the free tier.

Uses the Generative Language API (`generateContent`) with an API key. The vision
provider looks at the actual palm photo and returns structured observations that
flow into the deterministic interpretation engine, so the reading responds to the
real palm while staying grounded (no free-form fortune-telling). All calls raise
ProviderError on any problem, so the registry's bounded fallback drops back to the
mock rather than failing the request.

Config:
    GEMINI_API_KEY   your free key from https://aistudio.google.com/apikey
    GEMINI_MODEL     model id (default gemini-2.0-flash)
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request

from .base import ProviderError, TextProvider, VisionProvider
from ..schemas.ai import Observation, PalmObservation, Reading, Storyboard
from ..services.storyboard import compose

try:
    from ...palmistry.schemas.interpretation import Interpretation  # type: ignore
except Exception:  # pragma: no cover - import path shim
    from palmistry.schemas.interpretation import Interpretation  # type: ignore

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_FEATURES = ["heart_line", "head_line", "life_line", "fate_line", "sun_line"]
# the vocabulary the interpretation engine understands (keep the model on-vocabulary)
_VOCAB = "long, short, deep, faint, clear, strong, weak, curved, straight, upward, sloping, chained, broken, forked, wavy, absent"


def _model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()


def _call(parts: list, max_tokens: int = 900, temperature: float = 0.7) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise ProviderError("GEMINI_API_KEY is not set")
    url = _ENDPOINT.format(model=_model()) + "?key=" + key
    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise ProviderError(f"Gemini HTTP {e.code}: {e.read()[:200]!r}")
    except Exception as e:
        raise ProviderError(f"Gemini call failed: {e}")
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise ProviderError(f"Gemini returned no content: {str(data)[:200]}")


def _json(text: str):
    text = (text or "").replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        if not m:
            raise ProviderError("Gemini did not return JSON")
        return json.loads(m.group(0))


class GeminiVisionProvider(VisionProvider):
    name = "gemini"

    def observe(self, image: bytes, hand: str) -> PalmObservation:
        b64 = base64.b64encode(image).decode()
        prompt = (
            "You are assisting an ENTERTAINMENT palmistry app. Look at this photo of a "
            f"{hand} palm and DESCRIBE what you actually see for each of these lines: "
            "heart_line, head_line, life_line, fate_line, sun_line. "
            "Describe only what is visible (length, depth, curve, breaks, chains, forks); "
            "do NOT interpret meaning, predict the future, or mention health/lifespan. "
            f"Use plain descriptive words from this list where they fit: {_VOCAB}. "
            "If a line isn't visible, say 'absent' or 'faint'. "
            'Return ONLY JSON: {"observations":[{"feature":"heart_line",'
            '"observation":"<short visible description using the words above>",'
            '"confidence":<0..1 how clearly you could SEE it>}, ...]} '
            "with one entry per line, feature values exactly as listed."
        )
        parts = [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]
        obj = _json(_call(parts, max_tokens=700, temperature=0.4))
        items = obj.get("observations", obj if isinstance(obj, list) else [])
        obs = []
        for it in items:
            feat = str(it.get("feature", "")).strip().lower().replace(" ", "_")
            if feat not in _FEATURES:
                continue
            try:
                conf = float(it.get("confidence", 0.6))
            except (TypeError, ValueError):
                conf = 0.6
            obs.append(Observation(feature=feat,
                                   observation=str(it.get("observation", ""))[:300],
                                   confidence=max(0.0, min(1.0, conf))))
        if not obs:
            raise ProviderError("Gemini vision returned no usable observations")
        return PalmObservation(hand=hand, observations=obs)


class GeminiTextProvider(TextProvider):
    name = "gemini"

    def write_reading(self, interpretation: Interpretation) -> Reading:
        prompt = (
            "You are a warm, playful palmistry storyteller for an ENTERTAINMENT app. "
            "Using ONLY the grounded interpretation JSON below (do not invent new palm "
            "features, do not predict the future, no health/lifespan/medical/financial/legal "
            "claims), write a light, encouraging reading. "
            'Return ONLY JSON with keys: title (short), snapshot (1 sentence), '
            'sections (object with keys "heart","mind","career", each 1-2 sentences), '
            'strengths (array of short phrases), challenges (array), themes (array), '
            "story (2-3 warm sentences). Keep it kind and non-deterministic.\n\n"
            + interpretation.model_dump_json()
        )
        obj = _json(_call([{"text": prompt}], max_tokens=900, temperature=0.8))
        # be forgiving about shape
        return Reading(
            title=str(obj.get("title", "Your palm story"))[:120],
            snapshot=str(obj.get("snapshot", interpretation.summary if hasattr(interpretation, "summary") else ""))[:400],
            sections={k: str(v)[:600] for k, v in (obj.get("sections") or {}).items()},
            strengths=[str(x)[:80] for x in (obj.get("strengths") or [])][:6],
            challenges=[str(x)[:80] for x in (obj.get("challenges") or [])][:6],
            themes=[str(x)[:80] for x in (obj.get("themes") or [])][:6],
            story=str(obj.get("story", ""))[:1200],
        )

    def storyboard(self, reading: Reading) -> Storyboard:
        # Keep the deterministic 4-beat composer (reliable + already tuned);
        # the narrative it uses is now Gemini-written, so the comic follows the real reading.
        return compose(reading)
