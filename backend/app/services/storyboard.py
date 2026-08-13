"""Storyboard composition — the deliberate 'visual grammar' of a palm story.

Turns a Reading into a coherent four-panel comic arc, deterministically. This is
the scaffolding the mock TextProvider fills, and the same structure the HF prompt
asks the model to honour, so every storyboard — mock or real — has:

  * a clear four-beat arc:   setup → rising → turn → resolution
  * a consistent CHARACTER repeated across panels (so an image model keeps the
    same protagonist panel to panel)
  * a palette + art style chosen from the reading's dominant theme
  * a recurring palmistry motif: a glowing palm whose lines become the world

Nothing here is random: the same reading always yields the same storyboard.
"""
from ..schemas.ai import Panel, Reading, Storyboard, StoryboardStyle

# --- palette presets, keyed by the reading's dominant theme ---
PALETTES = {
    "Freedom and choice": "indigo dusk lit with gold, wide open sky",
    "Connection": "warm rose and amber, soft candlelight",
    "Depth over speed": "deep teal and slate, quiet starlight",
    "Vitality": "sunrise orange and coral, bright and alive",
    "Adventure": "sea-blue and sand, horizon light",
    "Direction": "midnight blue with a single gold beam",
    "Creativity": "violet and turquoise, playful glow",
    "Expression": "magenta and gold, stage-lit warmth",
    "_default": "twilight indigo and warm gold",
}

# --- the 'a line becomes a place' metaphor, keyed by dominant theme ---
# (rising_place, turning_threshold)
METAPHORS = {
    "Freedom and choice": ("an open road forking beneath a vast sky", "a crossroads where two paths of light diverge"),
    "Connection": ("a warm bridge of light joining two shores", "two lanterns almost touching across a gap"),
    "Depth over speed": ("a long winding road into distant hills", "a deep still river the traveller must cross"),
    "Vitality": ("a bright river rushing with light", "a steep sunlit trail rising into cloud"),
    "Adventure": ("a coastline opening onto the horizon", "a mountain pass under drifting clouds"),
    "Direction": ("a single star-lit path leading onward", "a lighthouse beam sweeping the dark"),
    "Creativity": ("a garden of impossible, glowing blooms", "a doorway of light in a plain wall"),
    "Expression": ("a wide stage washed in warm light", "a sky waiting to be written with colour"),
    "_default": ("a path of soft light unrolling ahead", "a threshold of gentle light"),
}

# --- protagonist mood adjective, keyed by the reading's leading strength ---
MOODS = {
    "Warmth in relationships": "warm-hearted and open",
    "Considered decision-making": "thoughtful and calm",
    "Resilience": "steady and unhurried",
    "Depth of feeling": "quietly deep",
    "Independence": "self-possessed",
    "Creativity": "bright-eyed and inventive",
    "Clarity": "clear and grounded",
    "Curiosity": "curious and searching",
    "_default": "quietly determined",
}


def _first(items: list[str], default: str) -> str:
    return items[0] if items else default


def compose(reading: Reading) -> Storyboard:
    theme = _first(reading.themes, "_default")
    palette = PALETTES.get(theme, PALETTES["_default"])
    rising_place, turning_threshold = METAPHORS.get(theme, METAPHORS["_default"])
    mood_adj = MOODS.get(_first(reading.strengths, "_default"), MOODS["_default"])
    theme_l = (theme if theme != "_default" else "their own quiet path").lower()

    # one consistent character description, repeated in every panel's visual
    character = f"a lone traveller with a small lantern, {mood_adj}"

    style = StoryboardStyle(palette=palette, character=character)

    panels = [
        Panel(
            panel=1, beat="setup",
            setting="a quiet dark just before dawn",
            subject=character, shot="wide establishing shot", mood="curious, hushed",
            visual=(f"{character} discovers a softly glowing palm held open, its lines "
                    f"shimmering like constellations; {palette}"),
            caption="It began with a light in the palm.",
        ),
        Panel(
            panel=2, beat="rising",
            setting=rising_place, subject=character, shot="medium tracking shot",
            mood="warm, unfolding",
            visual=(f"the palm's brightest line unfurls into {rising_place}; {character} "
                    f"steps forward along it; {palette}"),
            caption=f"One line became the way — toward {theme_l}.",
        ),
        Panel(
            panel=3, beat="turn",
            setting=turning_threshold, subject=character, shot="dramatic low angle",
            mood="charged, pivotal",
            visual=(f"{turning_threshold}; {character} pauses where the fate line fades, "
                    f"deciding; {palette}"),
            caption="Where the path faded, a choice appeared.",
        ),
        Panel(
            panel=4, beat="resolution",
            setting="an open horizon at first light", subject=character,
            shot="wide, hopeful", mood="bright, resolved",
            visual=(f"{character} walks their chosen path toward {theme_l} as dawn breaks; "
                    f"{palette}"),
            caption="They chose their own, and walked on.",
        ),
    ]

    logline = (f"A traveller reads the {theme_l} written in their palm "
               f"and chooses their own path.")

    return Storyboard(title=reading.title, logline=logline, style=style, panels=panels)
