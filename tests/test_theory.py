"""Checks for scales, chords and interval names. Run with:  python tests/test_theory.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fretboard import note_name, pitch_class  # noqa: E402
from theory import CHORDS, SCALES, highlight_set, interval_name, members  # noqa: E402


def names(pcs):
    return sorted(note_name(p) for p in pcs)


def test_chords():
    g = pitch_class("G")
    assert names(members(g, CHORDS["Major"][1])) == ["B", "D", "G"]
    assert names(members(pitch_class("D"), CHORDS["7"][1])) == ["A", "C", "D", "F#"]
    assert names(members(pitch_class("A"), CHORDS["Minor"][1])) == ["A", "C", "E"]


def test_scales():
    assert names(highlight_set("Scale", pitch_class("G"), "Mixolydian", "Major")) == \
        ["A", "B", "C", "D", "E", "F", "G"]
    assert names(highlight_set("Scale", pitch_class("E"), "Minor pentatonic", "Major")) == \
        ["A", "B", "D", "E", "G"]
    assert highlight_set("None", 0, "Major", "Major") == set()
    for name, steps in SCALES.items():
        assert steps[0] == 0 and steps == sorted(steps), name


def test_intervals():
    g = pitch_class("G")
    assert interval_name(g, g) == "1"
    assert interval_name(pitch_class("D"), g) == "5"
    assert interval_name(pitch_class("F"), g) == "♭7"
    assert interval_name(pitch_class("Bb"), g) == "♭3"


if __name__ == "__main__":
    for fn_name, fn in list(globals().items()):
        if fn_name.startswith("test_"):
            fn()
            print("ok ", fn_name)
    print("All checks passed.")
