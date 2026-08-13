"""Personality signature — turns a reading into an evocative archetype
('The Warm-Hearted Guardian') plus a one-line essence of who they are.

Deterministic: derived from the reading's dominant theme (refined by its leading
strength), so the same reading always yields the same signature. Used to headline
the written reading AND to frame the comic, so both tell the story of *this*
person rather than a generic arc.
"""

# theme -> (archetype name, essence line spoken to the person)
_ARCHETYPES = {
    "Connection":        ("The Warm-Hearted Guardian", "You lead with the heart — people feel safe in your warmth."),
    "Adventure":         ("The Restless Wanderer", "You're built for horizons — always reaching for the next spark."),
    "Depth over speed":  ("The Deep Current", "You move slow and think deep — nothing about you is shallow."),
    "Creativity":        ("The Dreaming Maker", "You see what isn't there yet, and you bring it to life."),
    "Direction":         ("The North-Star Navigator", "You carry an inner compass — you tend to know where you're headed."),
    "Expression":        ("The Bright Voice", "You were made to be seen and heard — you light up a room."),
    "Freedom and choice": ("The Untethered Soul", "No fixed track for you — you carve your own path."),
    "Vitality":          ("The Living Flame", "You run on energy and heart — people feel it when you walk in."),
    "Steadiness":        ("The Quiet Anchor", "Steady, grounded, dependable — the calm others lean on."),
    "Growth":            ("The Ever-Becoming", "You're always evolving — never quite the same person twice."),
    "Change":            ("The Shapeshifter", "You bend with life instead of breaking — adaptable to your core."),
    "Renewal":           ("The Phoenix Heart", "You rise again and again — endings are just beginnings for you."),
    "Exploration":       ("The Far-Seeker", "Curiosity is your engine — you're always reaching past the edge."),
}
_DEFAULT = ("The Quiet Seeker", "You walk a path that's entirely your own.")


def derive_signature(themes, strengths):
    """Return (archetype_name, essence_line) for a reading's themes/strengths."""
    name, essence = _DEFAULT
    for t in (themes or []):
        if t in _ARCHETYPES:
            name, essence = _ARCHETYPES[t]
            break
    # weave the leading strength into the essence for a touch more specificity
    if strengths:
        essence = essence.rstrip(".") + f", with {strengths[0].lower()} at your core."
    return name, essence


def apply_signature(reading) -> None:
    """Headline a Reading with its archetype: title becomes the archetype,
    the essence leads the snapshot. Mutates in place."""
    name, essence = derive_signature(reading.themes, reading.strengths)
    reading.title = name
    opening = reading.snapshot or ""
    reading.snapshot = (essence + " " + opening).strip()
