"""Scales, chords and intervals. No UI code here, so it can be tested with plain Python.

Everything works in pitch classes (0-11, C=0): a scale or chord is a list of
semitone steps above its root, e.g. a major chord is [0, 4, 7] (root, major 3rd, 5th).
"""

# Name shown for each interval above the root (0 = the root itself).
INTERVAL_NAMES = ["1", "♭2", "2", "♭3", "3", "4", "♭5", "5", "♭6", "6", "♭7", "7"]

SCALES = {
    "Major": [0, 2, 4, 5, 7, 9, 11],
    "Natural minor": [0, 2, 3, 5, 7, 8, 10],
    "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "Dorian": [0, 2, 3, 5, 7, 9, 10],
    "Major pentatonic": [0, 2, 4, 7, 9],
    "Minor pentatonic": [0, 3, 5, 7, 10],
    "Blues": [0, 3, 5, 6, 7, 10],
}

# Chord name -> (symbol added after the root, intervals). "G" + "m7" = "Gm7".
CHORDS = {
    "Major": ("", [0, 4, 7]),
    "Minor": ("m", [0, 3, 7]),
    "7": ("7", [0, 4, 7, 10]),
    "Major 7": ("maj7", [0, 4, 7, 11]),
    "Minor 7": ("m7", [0, 3, 7, 10]),
    "6": ("6", [0, 4, 7, 9]),
    "Minor 6": ("m6", [0, 3, 7, 9]),
    "sus2": ("sus2", [0, 2, 7]),
    "sus4": ("sus4", [0, 5, 7]),
    "Diminished": ("dim", [0, 3, 6]),
    "Augmented": ("aug", [0, 4, 8]),
    "9": ("9", [0, 2, 4, 7, 10]),
}

HIGHLIGHT_MODES = ["None", "Scale", "Chord"]


def members(root_pc: int, intervals) -> set[int]:
    """Pitch classes in a scale/chord: root G (7) + major chord -> {7, 11, 2} (G, B, D)."""
    return {(root_pc + i) % 12 for i in intervals}


def interval_name(pc: int, root_pc: int) -> str:
    """The note's role relative to the root: D over a G root -> '5'."""
    return INTERVAL_NAMES[(pc - root_pc) % 12]


def highlight_set(mode: str, root_pc: int, scale: str, chord: str) -> set[int]:
    """Pitch classes to light up for the chosen highlight mode (empty for 'None')."""
    if mode == "Scale":
        return members(root_pc, SCALES[scale])
    if mode == "Chord":
        return members(root_pc, CHORDS[chord][1])
    return set()
