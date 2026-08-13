"""Comic rendering.

`svg_panel` is a self-contained, offline, deterministic renderer that draws a
real comic panel — a recurring character, a palm-spirit mascot, a narrator
caption box with the reading's own text, and a speech bubble — one per narrative
beat. Because the text is drawn as crisp SVG (not baked into AI art), the words
are always legible and correct. It is the guaranteed fallback and what the mock
image provider uses, so a comic ALWAYS renders with no network and no image API.

`render_comic` orchestrates a whole storyboard: it asks the configured image
provider to render each panel and, on ANY failure, drops that single panel to the
SVG fallback — the comic never fails as a whole.
"""
import base64

from ..schemas.ai import Comic, ComicPanel, Panel, Storyboard, StoryboardStyle

# palette keyword → (background, mid, accent)
_PALETTE_COLORS = [
    (("rose", "amber", "warm", "magenta", "candle"), ("#3a1d2a", "#c65b6b", "#F6D96B")),
    (("indigo", "twilight", "midnight", "violet", "blue"), ("#20193c", "#4B3FA8", "#C0902B")),
    (("teal", "slate", "sea", "star"), ("#122a30", "#2f7d5b", "#E9C46A")),
    (("orange", "coral", "sunrise", "sunlit", "alive"), ("#3a1c14", "#e0794c", "#F6D96B")),
]

# per-beat: narrator caption tag, character expression, mascot one-liner, bubble kind
_BEATS = {
    "setup":      ("The palm",  "curious",  "Oh \u2014 light!", "thought"),
    "rising":     ("The path",  "hopeful",  "This way\u2026",   "speech"),
    "turn":       ("The choice", "wonder",  "Which path?",      "thought"),
    "resolution": ("The dawn",  "happy",    "Onward!",          "speech"),
}


def _colors(palette: str):
    p = (palette or "").lower()
    for keys, cols in _PALETTE_COLORS:
        if any(k in p for k in keys):
            return cols
    return ("#20193c", "#4B3FA8", "#C0902B")


def _esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _wrap(text: str, width: int) -> list:
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3] or [""]


def _character(cx: int, cy: int, expr: str, accent: str) -> str:
    """A simple, friendly, consistent protagonist. Expression varies by beat."""
    mouths = {
        "curious": f"<circle cx='{cx}' cy='{cy+8}' r='2.4' fill='#5a3324'/>",
        "hopeful": f"<path d='M{cx-6} {cy+6} Q{cx} {cy+12} {cx+6} {cy+6}' stroke='#5a3324' stroke-width='1.8' fill='none' stroke-linecap='round'/>",
        "wonder":  f"<path d='M{cx-5} {cy+8} L{cx+5} {cy+8}' stroke='#5a3324' stroke-width='1.8' stroke-linecap='round'/>",
        "happy":   f"<path d='M{cx-7} {cy+5} Q{cx} {cy+14} {cx+7} {cy+5}' stroke='#5a3324' stroke-width='2' fill='none' stroke-linecap='round'/>",
    }
    mouth = mouths.get(expr, mouths["hopeful"])
    return (
        # body
        f"<path d='M{cx-16} {cy+70} Q{cx-18} {cy+30} {cx} {cy+26} Q{cx+18} {cy+30} {cx+16} {cy+70} Z' fill='{accent}' opacity='0.92'/>"
        f"<rect x='{cx-16}' y='{cy+64}' width='32' height='10' fill='{accent}' opacity='0.65'/>"
        # neck + head
        f"<rect x='{cx-4}' y='{cy+18}' width='8' height='10' fill='#e7b58c'/>"
        f"<circle cx='{cx}' cy='{cy}' r='18' fill='#f0c9a0'/>"
        # hair
        f"<path d='M{cx-18} {cy-2} Q{cx-16} {cy-22} {cx} {cy-20} Q{cx+16} {cy-22} {cx+18} {cy-2} Q{cx+8} {cy-12} {cx} {cy-11} Q{cx-8} {cy-12} {cx-18} {cy-2} Z' fill='#4a3226'/>"
        # eyes
        f"<circle cx='{cx-6}' cy='{cy-1}' r='2.1' fill='#2a2a2a'/><circle cx='{cx+6}' cy='{cy-1}' r='2.1' fill='#2a2a2a'/>"
        f"{mouth}"
    )


def _mascot(cx: int, cy: int, accent: str) -> str:
    """A recurring 'palm-spirit' mascot — a small glowing hand-sprite with a face."""
    return (
        f"<circle cx='{cx}' cy='{cy}' r='22' fill='{accent}' opacity='0.22'/>"          # halo
        f"<path d='M{cx-10} {cy+12} Q{cx-13} {cy-4} {cx-9} {cy-6} Q{cx-8} {cy-16} {cx-4} {cy-10} "
        f"Q{cx} {cy-20} {cx+2} {cy-10} Q{cx+7} {cy-17} {cx+8} {cy-6} Q{cx+13} {cy-6} {cx+11} {cy+8} "
        f"Q{cx+9} {cy+16} {cx} {cy+16} Q{cx-8} {cy+16} {cx-10} {cy+12} Z' fill='{accent}'/>"  # palm/flame body
        f"<circle cx='{cx-4}' cy='{cy-1}' r='1.7' fill='#2a2a2a'/><circle cx='{cx+4}' cy='{cy-1}' r='1.7' fill='#2a2a2a'/>"
        f"<path d='M{cx-3} {cy+4} Q{cx} {cy+7} {cx+3} {cy+4}' stroke='#2a2a2a' stroke-width='1.2' fill='none' stroke-linecap='round'/>"
    )


def _bubble(x: int, y: int, w: int, h: int, line: str, kind: str, tail_to: tuple) -> str:
    """A speech (pointer tail) or thought (dotted tail) bubble with centred text."""
    cx = x + w // 2
    tx, ty = tail_to
    if kind == "thought":
        tail = (f"<circle cx='{x+w//2}' cy='{y+h+5}' r='4'/><circle cx='{tx}' cy='{ty-4}' r='2.6'/>")
        tail = f"<g fill='#ffffff' stroke='#2a2a2a' stroke-width='1'>{tail}</g>"
    else:
        tail = (f"<path d='M{cx-6} {y+h-2} L{tx} {ty} L{cx+8} {y+h-2} Z' fill='#ffffff' stroke='#2a2a2a' stroke-width='1'/>")
    return (
        f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='11' fill='#ffffff' stroke='#2a2a2a' stroke-width='1.4'/>"
        f"{tail}"
        f"<text x='{cx}' y='{y+h//2+4}' fill='#2a2a2a' font-family='Comic Sans MS,Marker Felt,sans-serif' "
        f"font-size='11' font-weight='bold' text-anchor='middle'>{_esc(line)}</text>"
    )


def svg_panel(panel: Panel, style: StoryboardStyle) -> str:
    """Deterministic, offline comic panel → a data URL. 300x300 viewBox."""
    bg, mid, accent = _colors(style.palette)
    beat = panel.beat if panel.beat in _BEATS else "setup"
    tag, expr, mascot_line, kind = _BEATS[beat]
    cap_lines = _wrap(panel.caption, 42)
    cap_dy = "".join(
        f"<tspan x='150' dy='{16 if i else 0}'>{_esc(ln)}</tspan>" for i, ln in enumerate(cap_lines)
    )
    cap_h = 20 + 16 * len(cap_lines)

    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='480' height='480' viewBox='0 0 300 300'>"
        "<defs>"
        f"<linearGradient id='sky' x1='0' y1='0' x2='0' y2='1'>"
        f"<stop offset='0' stop-color='{mid}'/><stop offset='1' stop-color='{bg}'/></linearGradient>"
        "</defs>"
        # scene
        f"<rect width='300' height='300' fill='url(#sky)'/>"
        f"<ellipse cx='150' cy='300' rx='170' ry='60' fill='{accent}' opacity='0.10'/>"
        f"<line x1='0' y1='252' x2='300' y2='252' stroke='{accent}' stroke-width='1.5' opacity='0.35'/>"
        # characters
        f"{_character(118, 176, expr, accent)}"
        f"{_mascot(212, 168, accent)}"
        # mascot speech/thought bubble
        f"{_bubble(158, 120, 96, 30, mascot_line, kind, (206, 150))}"
        # narrator caption box (the reading's own words, crisp)
        f"<rect x='10' y='10' width='280' height='{cap_h}' rx='7' fill='#fdf6e3' stroke='#2a2a2a' stroke-width='1.2'/>"
        f"<text x='150' y='{28}' fill='#2a2a2a' font-family='Georgia,serif' font-size='12.5' text-anchor='middle'>{cap_dy}</text>"
        # beat tag + panel number
        f"<rect x='10' y='{cap_h+16}' width='{20+len(tag)*7}' height='20' rx='4' fill='{accent}'/>"
        f"<text x='18' y='{cap_h+30}' fill='#2a1a1a' font-family='Georgia,serif' font-size='12' font-weight='bold'>{_esc(tag)}</text>"
        f"<circle cx='284' cy='284' r='11' fill='#2a2a2a' opacity='0.75'/>"
        f"<text x='284' y='288' fill='{accent}' font-family='Georgia,serif' font-size='13' font-weight='bold' text-anchor='middle'>{panel.panel}</text>"
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def render_comic(storyboard: Storyboard, provider) -> Comic:
    panels = []
    for p in storyboard.panels:
        try:
            url = provider.render_panel(p, storyboard.style)
            source = getattr(provider, "name", "unknown")
            if not url:
                raise ValueError("empty url")
        except Exception:
            url = svg_panel(p, storyboard.style)   # guaranteed fallback
            source = "svg-fallback"
        panels.append(ComicPanel(panel=p.panel, caption=p.caption, image_url=url, source=source))
    return Comic(title=storyboard.title, provider=getattr(provider, "name", "unknown"), panels=panels)
