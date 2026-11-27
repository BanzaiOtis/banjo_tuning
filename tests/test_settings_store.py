"""Checks that settings are remembered, and that a bad file can't break the app.
Run with:  python tests/test_settings_store.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import settings_store  # noqa: E402


def temp_path():
    return os.path.join(tempfile.mkdtemp(), "settings.json")


def test_defaults_when_no_file():
    assert settings_store.load(temp_path()) == settings_store.DEFAULTS


def test_round_trip():
    path = temp_path()
    s = dict(settings_store.DEFAULTS, capo=3, highlight="Chord", chord="7", root=2, volume=0.5,
             orientation="Sideways", labels="Intervals", tuning_key="custom:Mine")
    settings_store.save(s, path)
    assert settings_store.load(path) == s


def test_bad_values_fall_back():
    path = temp_path()
    with open(path, "w") as f:
        json.dump({"capo": 99, "volume": "loud", "flats": 1, "scale": "Nope", "root": 4,
                   "fifth_start": 7, "fifth_capo": 5}, f)
    s = settings_store.load(path)
    assert s["capo"] == 0 and s["volume"] == 0.8 and s["flats"] is False and s["scale"] == "Major"
    assert s["root"] == 4 and s["fifth_start"] == 7
    assert s["fifth_capo"] == 0          # below where the 5th string starts, so dropped
    with open(path, "w") as f:
        f.write("not json")
    assert settings_store.load(path) == settings_store.DEFAULTS


if __name__ == "__main__":
    for fn_name, fn in list(globals().items()):
        if fn_name.startswith("test_"):
            fn()
            print("ok ", fn_name)
    print("All checks passed.")
