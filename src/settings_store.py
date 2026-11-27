"""Remembers the app's settings between launches (tuning, capos, display and sound options).

Saved as settings.json next to tunings.json in the app's private data folder.
Every value is checked when loading, so an old or damaged file can't break the app:
anything missing or invalid just falls back to its default.
"""
import json
import os

from fretboard import CAPO_CHOICES, DEFAULT_FIFTH_START, FIFTH_START_CHOICES, NUM_FRETS, TRANSPOSE_RANGE
from theory import CHORDS, HIGHLIGHT_MODES, SCALES

RING_CHOICES = {"Short": 0.4, "Medium": 0.8, "Full": None}   # seconds a note rings (None = whole sound)
PLAY_ON_CHOICES = ["Tap", "Long-press"]
LABEL_CHOICES = ["Notes", "Intervals"]
ORIENTATION_CHOICES = ["Vertical", "Sideways"]

DEFAULTS = {
    "tuning_key": "default:Open G",
    "flats": False,
    "fifth_start": DEFAULT_FIFTH_START,
    "capo": 0,
    "fifth_capo": 0,
    "transpose": 0,
    "tones": False,
    "volume": 0.8,
    "ring": "Full",
    "play_on": "Tap",
    "highlight": "None",
    "root": 7,                 # G
    "scale": "Major",
    "chord": "Major",
    "labels": "Notes",
    "orientation": "Vertical",
}


def default_path() -> str:
    base = os.getenv("FLET_APP_STORAGE_DATA") or os.path.join(os.path.expanduser("~"), ".banjo_tuning")
    return os.path.join(base, "settings.json")


def _int_in(value, allowed) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in allowed


VALIDATORS = {
    "tuning_key": lambda v: isinstance(v, str) and ":" in v,
    "flats": lambda v: isinstance(v, bool),
    "fifth_start": lambda v: _int_in(v, FIFTH_START_CHOICES),
    "capo": lambda v: _int_in(v, CAPO_CHOICES),
    "fifth_capo": lambda v: _int_in(v, range(0, NUM_FRETS + 1)),
    "transpose": lambda v: _int_in(v, range(-TRANSPOSE_RANGE, TRANSPOSE_RANGE + 1)),
    "tones": lambda v: isinstance(v, bool),
    "volume": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1,
    "ring": lambda v: v in RING_CHOICES,
    "play_on": lambda v: v in PLAY_ON_CHOICES,
    "highlight": lambda v: v in HIGHLIGHT_MODES,
    "root": lambda v: _int_in(v, range(12)),
    "scale": lambda v: v in SCALES,
    "chord": lambda v: v in CHORDS,
    "labels": lambda v: v in LABEL_CHOICES,
    "orientation": lambda v: v in ORIENTATION_CHOICES,
}


def load(path: str | None = None) -> dict:
    """Saved settings merged over the defaults; bad or missing values use the default."""
    settings = dict(DEFAULTS)
    try:
        with open(path or default_path(), encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return settings
    if isinstance(saved, dict):
        for key, check in VALIDATORS.items():
            if key in saved and check(saved[key]):
                settings[key] = saved[key]
    # The 5th-string capo has to sit above where the 5th string starts.
    if settings["fifth_capo"] and settings["fifth_capo"] <= settings["fifth_start"]:
        settings["fifth_capo"] = 0
    return settings


def save(settings: dict, path: str | None = None) -> None:
    path = path or default_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({k: settings[k] for k in DEFAULTS if k in settings}, f, indent=2)
    os.replace(tmp, path)
