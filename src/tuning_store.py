"""Saving and loading the user's tunings: custom tunings, and which tunings appear in the menu.

Everything is kept in a small JSON file (tunings.json) in the app's private data
folder. Flet tells the app where that folder is through the FLET_APP_STORAGE_DATA
environment variable (on your PC during `flet run` it's src/.flet/storage/data).
No UI code lives here, so it can be tested with plain Python.
"""
import json
import os
from collections import namedtuple

from tunings import TUNINGS as DEFAULT_TUNINGS

# Note spellings offered when building a custom tuning.
NOTE_CHOICES = ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb",
                "G", "G#", "Ab", "A", "A#", "Bb", "B"]
MAX_NAME_LENGTH = 30

# One menu entry. key is "default:<name>" or "custom:<name>", so a name can't clash across groups.
Entry = namedtuple("Entry", "key group name strings")


def default_path() -> str:
    base = os.getenv("FLET_APP_STORAGE_DATA") or os.path.join(os.path.expanduser("~"), ".banjo_tuning")
    return os.path.join(base, "tunings.json")


def key_for(group: str, name: str) -> str:
    return f"{group}:{name}"


def valid_notes(notes) -> bool:
    return isinstance(notes, (list, tuple)) and len(notes) == 5 and all(n in NOTE_CHOICES for n in notes)


class TuningStore:
    def __init__(self, path: str | None = None):
        self.path = path or default_path()
        self.custom = {}      # name -> (5th, 4th, 3rd, 2nd, 1st), in the order they were added
        self.hidden = set()   # keys of tunings left out of the menu
        self.load()

    # ---------- file ----------
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return  # no file yet (first run) or unreadable: start fresh
        for name, notes in (data.get("custom") or {}).items():
            if isinstance(name, str) and name.strip() and valid_notes(notes):
                self.custom[name] = tuple(notes)
        known = {e.key for e in self.all_entries()}
        self.hidden = {k for k in data.get("hidden", []) if k in known}
        self.ensure_some_visible()

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"custom": {n: list(s) for n, s in self.custom.items()},
                       "hidden": sorted(self.hidden)}, f, indent=2)
        os.replace(tmp, self.path)  # swap in whole, so a crash can't leave half a file

    # ---------- reading ----------
    def all_entries(self) -> list[Entry]:
        return ([Entry(key_for("default", n), "default", n, s) for n, s in DEFAULT_TUNINGS.items()]
                + [Entry(key_for("custom", n), "custom", n, s) for n, s in self.custom.items()])

    def visible_entries(self) -> list[Entry]:
        return [e for e in self.all_entries() if e.key not in self.hidden]

    def is_visible(self, key: str) -> bool:
        return key not in self.hidden

    def strings_for(self, key: str):
        for e in self.all_entries():
            if e.key == key:
                return e.strings
        raise KeyError(key)

    # ---------- changing ----------
    def set_visible(self, key: str, visible: bool) -> bool:
        """Show or hide a tuning in the menu. Returns False if that would leave the menu empty."""
        if visible:
            self.hidden.discard(key)
            return True
        if key not in self.hidden and len(self.visible_entries()) <= 1:
            return False
        self.hidden.add(key)
        return True

    def set_all_visible(self, visible: bool, keep_key: str | None = None) -> None:
        """Show every tuning, or hide every tuning except keep_key (the menu can't be empty)."""
        if visible:
            self.hidden.clear()
        else:
            self.hidden = {e.key for e in self.all_entries() if e.key != keep_key}
            self.ensure_some_visible()

    def ensure_some_visible(self) -> None:
        if not self.visible_entries():
            self.hidden.discard(key_for("default", next(iter(DEFAULT_TUNINGS))))

    def validate(self, name: str, notes, old_name: str | None = None) -> str | None:
        """Return a message saying what's wrong, or None if the tuning can be saved."""
        name = (name or "").strip()
        if not name:
            return "Give the tuning a name."
        if len(name) > MAX_NAME_LENGTH:
            return f"Keep the name to {MAX_NAME_LENGTH} characters or fewer."
        if name in DEFAULT_TUNINGS:
            return f'"{name}" is already the name of a default tuning.'
        if name in self.custom and name != old_name:
            return f'You already have a custom tuning called "{name}".'
        if not valid_notes(notes):
            return "Choose a note for every string."
        return None

    def save_custom(self, name: str, notes, old_name: str | None = None) -> str:
        """Add a custom tuning, or update/rename one (old_name). Returns its menu key."""
        name = name.strip()
        notes = tuple(notes)
        if old_name is not None and old_name != name and old_name in self.custom:
            # Rename in place, keeping its position in the list.
            self.custom = {(name if n == old_name else n): (notes if n == old_name else s)
                           for n, s in self.custom.items()}
            old_key = key_for("custom", old_name)
            if old_key in self.hidden:
                self.hidden.discard(old_key)
                self.hidden.add(key_for("custom", name))
        else:
            self.custom[name] = notes
        return key_for("custom", name)

    def delete_custom(self, name: str) -> None:
        self.custom.pop(name, None)
        self.hidden.discard(key_for("custom", name))
        self.ensure_some_visible()
