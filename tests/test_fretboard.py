"""Checks for the music logic. Run with:  python tests/test_fretboard.py
(or `pytest` if you have it installed)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fretboard import at_capo, build_fretboard, fifth_capo_choices, transposed_names, note_name, open_midi, pitch_class, tuning_code, under_capo  # noqa: E402
from tunings import TUNINGS  # noqa: E402


def name_at(tuning, string_no, fret, fifth_start=5):
    pc = build_fretboard(TUNINGS[tuning], fifth_start=fifth_start)[fret][string_no]
    return None if pc is None else note_name(pc)


def test_pitch_class():
    assert pitch_class("C") == 0
    assert pitch_class("F#") == 6
    assert pitch_class("Bb") == 10
    assert pitch_class("g") == 7


def test_open_g_known_notes():
    assert name_at("Open G", 1, 0) == "D"
    assert name_at("Open G", 1, 2) == "E"
    assert name_at("Open G", 2, 1) == "C"
    assert name_at("Open G", 4, 12) == "D"   # octave
    assert name_at("Open G", 3, 4) == "B"


def test_fifth_string():
    assert name_at("Open G", 5, 0) is None   # no 5th string below fret 5
    assert name_at("Open G", 5, 4) is None
    assert name_at("Open G", 5, 5) == "G"    # its open note
    assert name_at("Open G", 5, 7) == "A"
    assert name_at("Open D", 5, 6) == "G"    # F# + 1


def test_fifth_string_other_start():
    assert name_at("Open G", 5, 6, fifth_start=7) is None
    assert name_at("Open G", 5, 7, fifth_start=7) == "G"
    assert name_at("Open G", 5, 9, fifth_start=7) == "A"
    assert name_at("Open G", 4, 3, fifth_start=7) == "F"  # other strings unaffected


def test_g_d_tuning():
    assert tuning_code(TUNINGS["G/D"]) == "gDGAD"


def test_every_tuning_builds():
    for name, strings in TUNINGS.items():
        board = build_fretboard(strings)
        assert len(board) == 26, name   # open + 25 frets
        assert len(strings) == 5, name


def test_real_pitches():
    # Open G sounds g4 D3 G3 B3 D4 (MIDI 67 50 55 59 62)
    assert [open_midi(n, s) for s, n in zip((5, 4, 3, 2, 1), TUNINGS["Open G"])] == [67, 50, 55, 59, 62]
    assert open_midi("C", 4) == 48     # Drop C: 4th string down to C3
    assert open_midi("C", 2) == 60     # Double C: 2nd string up to C4
    assert open_midi("F#", 5) == 66    # Open D: 5th string down to F#4
    assert open_midi("A", 5) == 69     # 5th string up to A4
    assert build_fretboard(TUNINGS["Open G"])[12][1] == 74   # D5, octave above open 1st


def test_capo():
    assert under_capo(4, 1, 2) and under_capo(1, 0, 2)
    assert not under_capo(4, 2, 2)          # the capo fret itself is playable
    assert not under_capo(5, 6, 7)          # main capo never covers the 5th string
    assert under_capo(5, 6, 0, fifth_capo=7) and at_capo(5, 7, 0, fifth_capo=7)
    assert not under_capo(4, 1, 0, fifth_capo=7)   # 5th-string capo leaves the others alone
    assert not under_capo(3, 0, 0)          # no capo
    assert at_capo(2, 3, 3) and not at_capo(5, 3, 3) and not at_capo(2, 0, 0)
    # Open G, capo 2: strings 4-1 sound E A C# E (an A chord)
    row = build_fretboard(TUNINGS["Open G"])[2]
    assert [note_name(row[s]) for s in (4, 3, 2, 1)] == ["E", "A", "C#", "E"]


def test_fifth_capo_choices():
    assert fifth_capo_choices(5) == [0] + list(range(6, 18))
    assert fifth_capo_choices(20) == [0, 21, 22, 23, 24, 25]


def test_transpose():
    assert transposed_names(TUNINGS["Open G"], 2) == ["A", "E", "A", "C#", "E"]
    assert transposed_names(TUNINGS["Open G"], -1, use_flats=True) == ["Gb", "Db", "Gb", "Bb", "Db"]
    up2 = build_fretboard(TUNINGS["Open G"], transpose=2)
    plain = build_fretboard(TUNINGS["Open G"])
    assert up2[0][4] == plain[0][4] + 2 == 52          # E3, not snapped to another octave
    assert up2[5][5] == plain[5][5] + 2                 # 5th string moves too
    assert build_fretboard(TUNINGS["Open G"], transpose=-3)[3][1] == plain[0][1]  # same note, 3 frets up


def test_tuning_code():
    assert tuning_code(TUNINGS["Open G"]) == "gDGBD"
    assert tuning_code(TUNINGS["Open D"]) == "f#DF#AD"


if __name__ == "__main__":
    for fn_name, fn in list(globals().items()):
        if fn_name.startswith("test_"):
            fn()
            print("ok ", fn_name)
    print("All checks passed.")
