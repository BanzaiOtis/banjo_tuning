"""Checks for saving/loading custom tunings and menu visibility. Run with:
    python tests/test_tuning_store.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tuning_store import TuningStore, key_for  # noqa: E402


def fresh_store():
    path = os.path.join(tempfile.mkdtemp(), "tunings.json")
    return TuningStore(path), path


def test_first_run_shows_all_defaults():
    store, _ = fresh_store()
    assert store.custom == {}
    assert len(store.visible_entries()) == 11
    assert store.visible_entries()[0].key == key_for("default", "Open G")


def test_add_save_and_reload():
    store, path = fresh_store()
    assert store.validate("Sawmill A", ["A", "E", "A", "D", "E"]) is None
    key = store.save_custom("Sawmill A", ["A", "E", "A", "D", "E"])
    assert key == "custom:Sawmill A"
    store.set_visible(key_for("default", "Old G"), False)
    store.save()
    again = TuningStore(path)
    assert again.custom == {"Sawmill A": ("A", "E", "A", "D", "E")}
    assert not again.is_visible(key_for("default", "Old G"))
    assert again.is_visible("custom:Sawmill A")


def test_validation():
    store, _ = fresh_store()
    store.save_custom("Mine", ["G", "D", "G", "B", "D"])
    assert store.validate("", ["G"] * 5)
    assert store.validate("Open G", ["G"] * 5)            # clashes with a default name
    assert store.validate("Mine", ["G"] * 5)              # duplicate custom name
    assert store.validate("Mine", ["G"] * 5, old_name="Mine") is None  # editing itself is fine
    assert store.validate("New", ["G", "D", "G", "B"])    # only 4 notes
    assert store.validate("New", ["G", "D", "G", "B", "H"])  # not a note


def test_rename_keeps_order_and_hidden_state():
    store, _ = fresh_store()
    store.save_custom("A", ["G"] * 5)
    store.save_custom("B", ["D"] * 5)
    store.set_visible("custom:A", False)
    store.save_custom("A2", ["C"] * 5, old_name="A")
    assert list(store.custom) == ["A2", "B"]
    assert store.custom["A2"] == ("C",) * 5
    assert not store.is_visible("custom:A2")


def test_menu_never_empty():
    store, _ = fresh_store()
    entries = store.visible_entries()
    for e in entries[:-1]:
        assert store.set_visible(e.key, False)
    assert not store.set_visible(entries[-1].key, False)   # refuses to hide the last one
    assert len(store.visible_entries()) == 1


def test_delete_last_visible_custom_restores_a_default():
    store, _ = fresh_store()
    store.save_custom("Only", ["G"] * 5)
    for e in store.all_entries():
        if e.group == "default":
            store.set_visible(e.key, False)
    store.delete_custom("Only")
    assert store.visible_entries()


def test_select_and_deselect_all():
    store, _ = fresh_store()
    store.save_custom("Mine", ["G"] * 5)
    store.set_all_visible(False, keep_key="custom:Mine")
    assert [e.key for e in store.visible_entries()] == ["custom:Mine"]
    store.set_all_visible(True)
    assert len(store.visible_entries()) == 12


def test_bad_file_is_ignored():
    store, path = fresh_store()
    with open(path, "w") as f:
        f.write("{not json")
    assert TuningStore(path).custom == {}
    with open(path, "w") as f:
        json.dump({"custom": {"ok": ["G", "D", "G", "B", "D"], "bad": ["X"]}, "hidden": ["nope:x"]}, f)
    s = TuningStore(path)
    assert list(s.custom) == ["ok"] and s.hidden == set()


if __name__ == "__main__":
    for fn_name, fn in list(globals().items()):
        if fn_name.startswith("test_"):
            fn()
            print("ok ", fn_name)
    print("All checks passed.")
