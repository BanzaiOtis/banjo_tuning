"""Music logic for the banjo fretboard: no UI code lives here.

Keeping this separate from main.py means you can test it with plain Python
(see tests/test_fretboard.py) without opening the app.

Two ways of numbering notes are used:
  * pitch class: 0-11 where C=0, C#=1 ... B=11 (the note's name, ignoring octave)
  * MIDI number: the exact pitch including octave, e.g. middle C (C4) = 60,
    the open 4th string in Open G (D3) = 50. pitch class = midi % 12.
Moving up one fret adds 1 to either.
"""

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
NATURALS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

NUM_FRETS = 25                 # frets shown on screen
DEFAULT_FIFTH_START = 5        # the short 5th string usually starts at the 5th fret
FIFTH_START_CHOICES = range(1, 13)  # frets the app lets you pick for it
STRING_ORDER = (5, 4, 3, 2, 1)  # left-to-right on screen, like a chord chart
MARKER_FRETS = {3, 5, 7, 10, 12, 15, 17, 19, 22, 24}  # usual inlay positions
CAPO_CHOICES = range(0, 13)    # 0 = no capo

# Open G (g4 D3 G3 B3 D4) as MIDI numbers. In other tunings each string is
# assumed to be retuned to the nearest pitch with the new note name.
STANDARD_MIDI = {5: 67, 4: 50, 3: 55, 2: 59, 1: 62}


def pitch_class(name: str) -> int:
    """'F#' -> 6, 'Bb' -> 10, 'g' -> 7. Accepts # / b or the ♯ / ♭ symbols."""
    name = name.strip()
    letter = name[0].upper()
    if letter not in NATURALS:
        raise ValueError(f"Not a note name: {name!r}")
    pc = NATURALS[letter]
    for accidental in name[1:]:
        if accidental in "#♯":
            pc += 1
        elif accidental in "b♭":
            pc -= 1
        else:
            raise ValueError(f"Not a note name: {name!r}")
    return pc % 12


def note_name(pc_or_midi: int, use_flats: bool = False) -> str:
    """6 -> 'F#' (or 'Gb' when use_flats is True). MIDI numbers work too."""
    return (FLAT_NAMES if use_flats else SHARP_NAMES)[pc_or_midi % 12]


def pretty(name: str) -> str:
    """'F#' -> 'F♯', 'Bb' -> 'B♭' for nicer display."""
    return name[0] + name[1:].replace("#", "♯").replace("b", "♭")


def uses_flats(strings) -> bool:
    """True if any open string in a tuning is written with a flat (e.g. G minor)."""
    return any("b" in s[1:] for s in strings)


def tuning_code(strings) -> str:
    """('G','D','G','B','D') -> 'gDGBD' (the banjo convention: 5th string in lowercase)."""
    fifth, *rest = strings
    return fifth[0].lower() + fifth[1:] + "".join(rest)


TRANSPOSE_RANGE = 12   # how far transpose mode goes each way, in semitones


def transposed_names(strings, semitones: int, use_flats: bool = False) -> list[str]:
    """('G','D','G','B','D'), +2 -> ['A','E','A','C#','E']: every string moved by the same amount."""
    return [note_name(pitch_class(n) + semitones, use_flats) for n in strings]


def open_midi(open_note: str, string_number: int) -> int:
    """The open string's exact pitch: the note with this name nearest to Open G's pitch."""
    standard = STANDARD_MIDI[string_number]
    up = (pitch_class(open_note) - standard) % 12   # 0..11 semitones up
    return standard + up if up <= 6 else standard + up - 12


def fretted_midi(open_note: str, string_number: int, fret: int,
                 fifth_start: int = DEFAULT_FIFTH_START, transpose: int = 0):
    """Exact pitch (MIDI number) at a fret, or None where the string doesn't exist.

    The 5th string only exists from `fifth_start` up (usually fret 5). Its open
    note sounds at that position, and each fret above it adds a semitone.
    """
    base = open_midi(open_note, string_number) + transpose
    if string_number == 5:
        if fret < fifth_start:
            return None
        return base + fret - fifth_start
    return base + fret


def build_fretboard(strings, num_frets: int = NUM_FRETS,
                    fifth_start: int = DEFAULT_FIFTH_START, transpose: int = 0):
    """Return one dict per fret (0 = open), mapping string number -> MIDI number or None.

    `strings` is the tuning written 5th string first, e.g. ("G", "D", "G", "B", "D").
    `transpose` raises (or, if negative, lowers) every string by that many semitones.
    """
    open_notes = dict(zip(STRING_ORDER, strings))
    return [
        {s: fretted_midi(open_notes[s], s, fret, fifth_start, transpose) for s in STRING_ORDER}
        for fret in range(num_frets + 1)
    ]


def _capo_for(string_number: int, capo: int, fifth_capo: int) -> int:
    """The main capo clamps the 4th-1st strings; the 5th string has its own (0 = none)."""
    return fifth_capo if string_number == 5 else capo


def under_capo(string_number: int, fret: int, capo: int, fifth_capo: int = 0) -> bool:
    """True for frets between the nut (or 5th-string start) and the capo: these can't be played."""
    c = _capo_for(string_number, capo, fifth_capo)
    return c > 0 and fret < c


def at_capo(string_number: int, fret: int, capo: int, fifth_capo: int = 0) -> bool:
    """True where a capo sits: these are the strings' new 'open' notes."""
    c = _capo_for(string_number, capo, fifth_capo)
    return c > 0 and fret == c


def fifth_capo_choices(fifth_start: int, num_frets: int = NUM_FRETS) -> list[int]:
    """Frets a 5th-string capo can go on: above where the string starts. 0 = none."""
    return [0] + list(range(fifth_start + 1, min(fifth_start + 12, num_frets) + 1))
