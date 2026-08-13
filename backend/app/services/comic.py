"""Comic rendering.

`svg_panel` is a self-contained, offline, deterministic renderer — a themed SVG
scene per narrative beat. It is the guaranteed fallback (and what the mock image
provider uses), so a comic ALWAYS renders even with no network and no image API.

`render_comic` orchestrates a whole storyboard: it asks the configured image
provider to render each panel and, on ANY failure, drops that single panel to the
SVG fallback — the comic never fails as a whole.
"""
import base64

from ..schemas.ai import Comic, ComicPanel, Panel, Storyboard, StoryboardStyle

# palette keyword → (background, mid, accent)
_PALETTE_COLORS = [
    (("rose", "amber", "warm", "magenta", "candle"), ("#2a1520", "#c65b6b", "#F6D96B")),
    (("indigo", "twilight", "midnight", "violet", "blue"), ("#191430", "#4B3FA8", "#C0902B")),
    (("teal", "slate", "sea", "star"), ("#102028", "#2f7d5b", "#E9C46A")),
    (("orange", "coral", "sunrise", "sunlit", "alive"), ("#2a1410", "#e0794c", "#F6D96B")),
]


def _colors(palette: str):
    p = (palette or "").lower()
    for keys, cols in _PALETTE_COLORS:
        if any(k in p for k in keys):
            return cols
    return ("#191430", "#4B3FA8", "#C0902B")


def _motif(beat: str, accent: str) -> str:
    """A simple beat-specific vignette (200x200 canvas)."""
    if beat == "setup":       # a glowing open palm / orb
        return (f"<circle cx='100' cy='96' r='46' fill='{accent}' opacity='0.85'/>"
                f"<circle cx='100' cy='96' r='66' fill='none' stroke='{accent}' stroke-width='2' opacity='0.4'/>")
    if beat == "rising":      # a winding road climbing away
        return (f"<path d='M40 165 C 90 140, 70 100, 120 80 S 150 40, 150 30' fill='none' "
                f"stroke='{accent}' stroke-width='6' stroke-linecap='round'/>")
    if beat == "turn":        # a fork of two paths
        return (f"<path d='M100 168 L100 110' stroke='{accent}' stroke-width='6' stroke-linecap='round'/>"
                f"<path d='M100 110 L58 52' stroke='{accent}' stroke-width='6' stroke-linecap='round'/>"
                f"<path d='M100 110 L146 52' stroke='{accent}' stroke-width='6' stroke-linecap='round' opacity='0.55'/>")
    # resolution: a rising sun over a horizon
    return (f"<line x1='24' y1='150' x2='176' y2='150' stroke='{accent}' stroke-width='3' opacity='0.6'/>"
            f"<circle cx='100' cy='150' r='40' fill='{accent}'/>")


def svg_panel(panel: Panel, style: StoryboardStyle) -> str:
    """Deterministic, offline SVG for one panel → a data URL."""
    bg, mid, accent = _colors(style.palette)
    beat = panel.beat or "setup"
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='400' viewBox='0 0 200 200'>"
        f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        f"<stop offset='0' stop-color='{mid}'/><stop offset='1' stop-color='{bg}'/></linearGradient></defs>"
        f"<rect width='200' height='200' fill='url(#g)'/>"
        f"{_motif(beat, accent)}"
        f"<circle cx='22' cy='22' r='13' fill='{bg}' opacity='0.85'/>"
        f"<text x='22' y='27' fill='{accent}' font-family='Georgia,serif' font-size='16' "
        f"font-weight='bold' text-anchor='middle'>{panel.panel}</text>"
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
