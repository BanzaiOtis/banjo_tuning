"""Banjo Tuning Helper: shows every note on a 5-string banjo neck for a chosen tuning.

Run on your PC with:   flet run src/main.py
"""
import os

import flet as ft

from fretboard import (
    CAPO_CHOICES,
    fifth_capo_choices,
    DEFAULT_FIFTH_START,
    FIFTH_START_CHOICES,
    MARKER_FRETS,
    NUM_FRETS,
    TRANSPOSE_RANGE,
    STRING_ORDER,
    at_capo,
    build_fretboard,
    note_name,
    open_midi,
    pretty,
    transposed_names,
    tuning_code,
    under_capo,
    uses_flats,
)
from tuning_store import NOTE_CHOICES, TuningStore, key_for

# Sound is optional: if the flet-audio package isn't installed the app still
# runs, it just greys out the Tones switch.
try:
    import flet_audio as fta
except ImportError:
    fta = None

# Colours (any "#RRGGBB" works, so tweak away)
WOOD = "#4A3324"          # normal fret cell
WOOD_DARK = "#2E1F16"     # open-string row and "no string here" cells
UNDER_CAPO = "#1F150F"    # frets between the nut and the capo
UNDER_CAPO_TEXT = "#6B5D52"  # greyed-out note names behind a capo
FRET_WIRE = "#9E9E9E"     # shows through the gaps between cells as fret lines
NUT = "#EDE6D6"
TEXT = "#F5F0E6"
MARKER = "#E8A33D"        # inlay frets: fret number and note names
HILITE = "#E8A33D"        # cells matching the note you tapped
HILITE_TEXT = "#1E1E1E"
CAPO_BG = "#A7B0BA"       # the capo bar
CAPO_TEXT = "#111111"
ERROR = "#FF8A80"

STRING_LABELS = {5: "5th", 4: "4th", 3: "3rd", 2: "2nd", 1: "1st"}
GROUP_LABELS = {"default": "Default tunings", "custom": "Custom tunings"}
CELL_HEIGHT = 36
FRET_COL_WIDTH = 36
CENTER = ft.Alignment(0, 0)


def main(page: ft.Page):
    page.title = "Banjo Tuning Helper"
    page.padding = 8
    page.theme_mode = ft.ThemeMode.DARK

    # On a PC, make the window phone-shaped so it previews like the real thing.
    if page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX):
        page.window.width = 420
        page.window.height = 860

    store = TuningStore()  # custom tunings + which tunings show in the menu, saved on the device
    start_key = key_for("default", "Open G")
    if not store.is_visible(start_key):
        start_key = store.visible_entries()[0].key

    # Everything the screen depends on. render() redraws from this.
    state = {
        "tuning_key": start_key,
        "flats": uses_flats(store.strings_for(start_key)),
        "selected": None,          # pitch class (0-11) the user tapped, or None
        "fifth_start": DEFAULT_FIFTH_START,
        "capo": 0,                 # capo on the 4th-1st strings, 0 = none
        "fifth_capo": 0,           # separate 5th-string capo, 0 = none
        "tones": False,
        "transposing": False,      # transpose mode: dragging the neck shifts the tuning
        "transpose": 0,            # semitones up (+) or down (-) applied to every string
        "drag": 0.0,               # drag distance not yet turned into a semitone step
        "panel_open": False,       # settings panel expanded?
        "managing": False,         # showing the Manage tunings screen?
        "editing": None,           # tuning being added/edited: {"old_name", "name", "notes", "error"}
        "confirm_delete": None,    # custom tuning name waiting for a second tap on delete
        "message": "",             # note shown on the Manage tunings screen
    }

    def current_strings():
        return store.strings_for(state["tuning_key"])

    def shown_strings():
        """The current tuning with any transposition applied, spelled with sharps or flats."""
        if state["transpose"] == 0:
            return list(current_strings())
        return transposed_names(current_strings(), state["transpose"], state["flats"])

    def entry_name():
        return state["tuning_key"].split(":", 1)[1]

    def persist():
        try:
            store.save()
        except OSError as err:
            state["message"] = f"Couldn't save your tunings: {err}"

    # ---------- sound ----------
    players = {}  # MIDI number -> Audio player, created the first time that note is played
    tones_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "tones")

    def tone_source(midi):
        """The sound's raw bytes, so the player never has to fetch a file
        (works in the phone preview and the built app). Falls back to the
        asset path if the file can't be read from here."""
        path = os.path.join(tones_dir, f"n{midi}.wav")
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError:
            return f"tones/n{midi}.wav"

    async def play_tone(midi):
        try:
            player = players.get(midi)
            if player is None:
                player = fta.Audio(src=tone_source(midi), autoplay=True)
                players[midi] = player
                page.services.append(player)  # autoplay starts it once it's loaded
                page.update()
            else:
                await player.play()  # restarts from the beginning
        except Exception as err:  # keep the app running if sound fails
            print("Could not play tone:", err)

    # ---------- fretboard event handlers ----------
    def on_tuning_select(e):
        key = e.control.value
        if key and not key.startswith("hdr:"):   # ignore taps on the group headings
            state["tuning_key"] = key
            state["flats"] = uses_flats(current_strings())
            state["transpose"] = 0
        render()

    def on_fifth_start_select(e):
        state["fifth_start"] = int(e.control.value)
        if state["fifth_capo"] not in fifth_capo_choices(state["fifth_start"]):
            state["fifth_capo"] = 0   # the 5th-string capo has to sit above where the string starts
        render()

    def on_fifth_capo_select(e):
        state["fifth_capo"] = int(e.control.value)
        render()

    def on_capo_select(e):
        state["capo"] = int(e.control.value)
        render()

    def on_flats_change(e):
        state["flats"] = e.control.value
        render()

    def on_tones_change(e):
        state["tones"] = e.control.value
        render()

    # ---------- transpose ----------
    STEP_PX = CELL_HEIGHT + 2   # drag one fret's height = one semitone

    def set_transpose(value):
        value = max(-TRANSPOSE_RANGE, min(TRANSPOSE_RANGE, value))
        if value != state["transpose"]:
            state["transpose"] = value
            render()

    def on_transposing_change(e):
        state["transposing"] = e.control.value
        if state["transposing"]:
            state["panel_open"] = False   # collapse settings so more of the neck shows
        render()

    def transpose_down(e):
        set_transpose(state["transpose"] - 1)

    def transpose_up(e):
        set_transpose(state["transpose"] + 1)

    def transpose_reset(e):
        set_transpose(0)

    def on_drag_start(e):
        state["drag"] = 0.0

    def on_drag_update(e):
        # Dragging down moves notes down the neck = strings tuned lower.
        delta = e.primary_delta
        if delta is None:
            delta = e.local_delta.y if e.local_delta else 0.0
        state["drag"] += delta
        steps = int(state["drag"] / STEP_PX)   # whole frets dragged so far (sign = direction)
        if steps:
            state["drag"] -= steps * STEP_PX
            set_transpose(state["transpose"] - steps)

    def save_transposed(e):
        t = state["transpose"]
        state.update(
            managing=True, confirm_delete=None, message="",
            editing={"old_name": None, "name": f"{entry_name()} {t:+d}" if t else entry_name(),
                     "notes": shown_strings(), "error": ""},
        )
        render()

    def toggle_settings(e):
        state["panel_open"] = not state["panel_open"]
        render()

    async def on_cell_click(e):
        midi = e.control.data
        pc = midi % 12
        state["selected"] = None if state["selected"] == pc else pc
        render()
        if state["tones"]:
            await play_tone(midi)

    # ---------- Manage tunings event handlers ----------
    def open_manage(e):
        state.update(managing=True, editing=None, confirm_delete=None, message="")
        render()

    def close_manage(e):
        state.update(managing=False, editing=None, confirm_delete=None, message="")
        render()

    def set_all(visible):
        store.set_all_visible(visible, keep_key=state["tuning_key"])
        state["message"] = "" if visible else "The current tuning stays ticked so the menu isn't empty."
        persist()
        render()

    def select_all(e):
        set_all(True)

    def deselect_all(e):
        set_all(False)

    def on_visible_change(e):
        if store.set_visible(e.control.data, e.control.value):
            state["message"] = ""
            persist()
        else:
            state["message"] = "At least one tuning has to stay in the menu."
        render()

    def start_add(e):
        state.update(editing={"old_name": None, "name": "", "notes": list(current_strings()), "error": ""},
                     confirm_delete=None)
        render()

    def start_edit(e):
        name = e.control.data
        state.update(editing={"old_name": name, "name": name, "notes": list(store.custom[name]), "error": ""},
                     confirm_delete=None)
        render()

    def on_edit_name(e):
        state["editing"]["name"] = e.control.value

    def on_edit_note(e):
        state["editing"]["notes"][e.control.data] = e.control.value

    def save_edit(e):
        ed = state["editing"]
        error = store.validate(ed["name"], ed["notes"], ed["old_name"])
        if error:
            ed["error"] = error
            render()
            return
        new_key = store.save_custom(ed["name"], ed["notes"], ed["old_name"])
        # Switch to a new tuning, or follow a renamed one that was showing.
        if ed["old_name"] is None or state["tuning_key"] == key_for("custom", ed["old_name"]):
            if ed["old_name"] is None:
                state["transpose"] = 0   # the new tuning already has any transposition built in
                state["transposing"] = False
            state["tuning_key"] = new_key
            state["flats"] = uses_flats(current_strings())
        state["editing"] = None
        persist()
        render()

    def cancel_edit(e):
        state["editing"] = None
        render()

    def on_delete(e):
        name = e.control.data
        if state["confirm_delete"] == name:
            store.delete_custom(name)
            state["confirm_delete"] = None
            persist()
        else:
            state["confirm_delete"] = name   # first tap: ask for a second
        render()

    # ---------- controls that stay on screen ----------
    tuning_dropdown = ft.Dropdown(label="Tuning", expand=True, on_select=on_tuning_select)
    fifth_start_dropdown = ft.Dropdown(
        label="5th string starts at fret",
        value=str(DEFAULT_FIFTH_START),
        expand=True,
        options=[ft.DropdownOption(key=str(f), text=str(f)) for f in FIFTH_START_CHOICES],
        on_select=on_fifth_start_select,
    )
    capo_dropdown = ft.Dropdown(
        label="Capo",
        value="0",
        expand=True,
        options=[ft.DropdownOption(key=str(f), text="None" if f == 0 else f"Fret {f}") for f in CAPO_CHOICES],
        on_select=on_capo_select,
    )
    fifth_capo_dropdown = ft.Dropdown(label="5th string capo", value="0", expand=True,
                                      on_select=on_fifth_capo_select)
    flats_switch = ft.Switch(label="Flats", value=state["flats"], on_change=on_flats_change)
    tones_switch = ft.Switch(
        label="Tones" if fta else "Tones (install flet-audio)",
        value=False,
        disabled=fta is None,
        on_change=on_tones_change,
    )
    transpose_switch = ft.Switch(label="Transpose mode", value=False, on_change=on_transposing_change)
    transpose_label = ft.Text(size=15, weight=ft.FontWeight.BOLD, expand=True, text_align=ft.TextAlign.CENTER)
    transpose_bar = ft.Container(
        visible=False,
        bgcolor=WOOD_DARK,
        border_radius=8,
        padding=ft.Padding(4, 2, 4, 2),
        content=ft.Row([
            ft.IconButton(icon=ft.Icons.REMOVE, tooltip="Down a semitone", on_click=transpose_down),
            transpose_label,
            ft.IconButton(icon=ft.Icons.ADD, tooltip="Up a semitone", on_click=transpose_up),
            ft.IconButton(icon=ft.Icons.RESTART_ALT, tooltip="Reset", on_click=transpose_reset),
            ft.IconButton(icon=ft.Icons.SAVE, tooltip="Save as custom tuning", on_click=save_transposed),
        ], spacing=0),
    )
    header = ft.Row(spacing=2)
    board = ft.ListView(expand=True, spacing=2)
    # Used in transpose mode. It's created once and reused, so a swipe in progress
    # isn't cut off when the notes are redrawn after each semitone step.
    neck_column = ft.Column(spacing=2)
    neck_gesture = ft.GestureDetector(
        content=neck_column,
        on_vertical_drag_start=on_drag_start,
        on_vertical_drag_update=on_drag_update,
    )
    board_area = ft.Container(expand=True, bgcolor=FRET_WIRE, content=board)
    manage_view = ft.ListView(expand=True, spacing=6, visible=False)

    # Collapsible settings: a slim bar showing the current tuning; tap it to open/close.
    summary_text = ft.Text(size=15, weight=ft.FontWeight.BOLD, expand=True)
    expand_icon = ft.Icon(ft.Icons.EXPAND_MORE)
    settings_bar = ft.Container(
        padding=ft.Padding(12, 8, 12, 8),
        bgcolor=WOOD_DARK,
        border_radius=8,
        ink=True,
        on_click=toggle_settings,
        content=ft.Row([ft.Icon(ft.Icons.TUNE, size=20), summary_text, expand_icon]),
    )
    settings_panel = ft.Column(
        visible=False,
        spacing=8,
        controls=[
            ft.Row([tuning_dropdown]),
            ft.Row([capo_dropdown, fifth_capo_dropdown]),
            ft.Row([fifth_start_dropdown]),
            ft.Row([flats_switch, tones_switch], spacing=24),
            transpose_switch,
            ft.TextButton("Manage tunings", icon=ft.Icons.EDIT, on_click=open_manage),
        ],
    )

    # ---------- building blocks: fretboard ----------
    def tuning_options():
        options = []
        for group, label in GROUP_LABELS.items():
            entries = [e for e in store.visible_entries() if e.group == group]
            if not entries:
                continue
            options.append(ft.DropdownOption(key=f"hdr:{group}", text=f"— {label} —", disabled=True))
            options += [ft.DropdownOption(key=e.key, text=f"{e.name}  ({tuning_code(e.strings)})")
                        for e in entries]
        return options

    def note_cell(midi, fret, string_no):
        capo, fifth_capo = state["capo"], state["fifth_capo"]
        if midi is None:   # no 5th string here
            return ft.Container(expand=1, height=CELL_HEIGHT, bgcolor=WOOD_DARK)
        if under_capo(string_no, fret, capo, fifth_capo):
            # behind a capo: shown greyed out, and can't be tapped
            return ft.Container(
                expand=1, height=CELL_HEIGHT, alignment=CENTER, bgcolor=UNDER_CAPO,
                content=ft.Text(pretty(note_name(midi, state["flats"])), size=15, color=UNDER_CAPO_TEXT),
            )
        selected = midi % 12 == state["selected"]
        capo_here = at_capo(string_no, fret, capo, fifth_capo)
        if selected:
            bg, color = HILITE, HILITE_TEXT
        elif capo_here:
            bg, color = CAPO_BG, CAPO_TEXT
        else:
            bg = WOOD_DARK if fret == 0 else WOOD
            color = MARKER if fret in MARKER_FRETS else TEXT
        bold = selected or capo_here or fret in MARKER_FRETS
        return ft.Container(
            expand=1,
            height=CELL_HEIGHT,
            alignment=CENTER,
            bgcolor=bg,
            border_radius=4 if selected else 0,
            ink=True,
            data=midi,
            on_click=on_cell_click,
            content=ft.Text(
                pretty(note_name(midi, state["flats"])),
                size=15,
                weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
                color=color,
            ),
        )

    def fret_row(fret, row):
        is_capo_row = fret > 0 and fret in (state["capo"], state["fifth_capo"])
        fret_label = ft.Container(
            width=FRET_COL_WIDTH,
            height=CELL_HEIGHT,
            alignment=CENTER,
            bgcolor=CAPO_BG if is_capo_row else WOOD_DARK,
            content=ft.Text(
                "Open" if fret == 0 else str(fret),
                size=11 if fret == 0 else 13,
                color=CAPO_TEXT if is_capo_row else (MARKER if fret in MARKER_FRETS else TEXT),
                weight=ft.FontWeight.BOLD if (is_capo_row or fret in MARKER_FRETS) else ft.FontWeight.NORMAL,
            ),
        )
        return ft.Row(spacing=2, controls=[fret_label] + [note_cell(row[s], fret, s) for s in STRING_ORDER])

    def header_cell(string_no, midi):
        return ft.Container(
            expand=1,
            alignment=CENTER,
            content=ft.Column(
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(STRING_LABELS[string_no], size=11),
                    ft.Text(pretty(note_name(midi, state["flats"])), size=16, weight=ft.FontWeight.BOLD),
                ],
            ),
        )

    # ---------- building blocks: Manage tunings screen ----------
    def edit_form():
        ed = state["editing"]
        note_pickers = [
            ft.Dropdown(
                label=STRING_LABELS[s],
                value=ed["notes"][i],
                expand=1,
                data=i,
                options=[ft.DropdownOption(key=n, text=pretty(n)) for n in NOTE_CHOICES],
                on_select=on_edit_note,
            )
            for i, s in enumerate(STRING_ORDER)
        ]
        controls = [
            ft.Text("New custom tuning" if ed["old_name"] is None else "Edit custom tuning",
                    size=16, weight=ft.FontWeight.BOLD),
            ft.TextField(label="Name", value=ed["name"], on_change=on_edit_name),
            ft.Text("Open notes, 5th string to 1st:", size=12),
            ft.Row(note_pickers, spacing=4),
        ]
        if ed["error"]:
            controls.append(ft.Text(ed["error"], color=ERROR))
        controls.append(ft.Row([
            ft.FilledButton("Save", icon=ft.Icons.CHECK, on_click=save_edit),
            ft.TextButton("Cancel", on_click=cancel_edit),
        ]))
        return ft.Container(
            bgcolor=WOOD_DARK, border_radius=8, padding=12,
            content=ft.Column(controls, spacing=10),
        )

    def tuning_row(entry):
        checkbox = ft.Checkbox(
            label=f"{entry.name}  ({tuning_code(entry.strings)})",
            value=store.is_visible(entry.key),
            data=entry.key,
            on_change=on_visible_change,
            expand=True,
        )
        if entry.group == "default":
            return ft.Row([checkbox])
        confirming = state["confirm_delete"] == entry.name
        return ft.Row([
            checkbox,
            ft.IconButton(icon=ft.Icons.EDIT, tooltip="Edit", data=entry.name, on_click=start_edit),
            ft.IconButton(
                icon=ft.Icons.DELETE_FOREVER if confirming else ft.Icons.DELETE_OUTLINE,
                icon_color=ERROR if confirming else None,
                tooltip="Tap again to delete" if confirming else "Delete",
                data=entry.name,
                on_click=on_delete,
            ),
        ])

    def manage_controls():
        controls = [
            ft.Row([
                ft.Text("Manage tunings", size=18, weight=ft.FontWeight.BOLD, expand=True),
                ft.FilledButton("Done", on_click=close_manage),
            ]),
            ft.Text("Ticked tunings appear in the menu.", size=12),
            ft.Row([
                ft.TextButton("Select all", icon=ft.Icons.CHECK_BOX, on_click=select_all),
                ft.TextButton("Deselect all", icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK, on_click=deselect_all),
            ]),
        ]
        if state["message"]:
            controls.append(ft.Text(state["message"], color=ERROR))
        if state["editing"]:
            controls.append(edit_form())
        entries = store.all_entries()
        for group, label in GROUP_LABELS.items():
            controls += [ft.Divider(), ft.Text(label, size=15, weight=ft.FontWeight.BOLD)]
            group_entries = [e for e in entries if e.group == group]
            controls += [tuning_row(e) for e in group_entries]
            if group == "custom":
                if not group_entries:
                    controls.append(ft.Text("None yet.", size=13, italic=True))
                if not state["editing"]:
                    controls.append(ft.TextButton("Add custom tuning", icon=ft.Icons.ADD, on_click=start_add))
        if state["confirm_delete"]:
            controls.append(ft.Text("Tap the red delete button again to delete.", size=12, color=ERROR))
        return controls

    # ---------- draw everything from `state` ----------
    def render():
        # The current tuning may have been hidden or deleted: fall back to the first one in the menu.
        visible_keys = [e.key for e in store.visible_entries()]
        if state["tuning_key"] not in visible_keys:
            state["tuning_key"] = visible_keys[0]
            state["flats"] = uses_flats(current_strings())
        flats_switch.value = state["flats"]

        strings = current_strings()
        tuning_dropdown.options = tuning_options()
        tuning_dropdown.value = state["tuning_key"]
        fifth_capo_dropdown.options = [
            ft.DropdownOption(key=str(f), text="None" if f == 0 else f"Fret {f}")
            for f in fifth_capo_choices(state["fifth_start"])
        ]
        fifth_capo_dropdown.value = str(state["fifth_capo"])

        managing = state["managing"]
        settings_bar.visible = not managing
        settings_panel.visible = state["panel_open"] and not managing
        transpose_switch.value = state["transposing"]
        transpose_bar.visible = state["transposing"] and not managing
        t = state["transpose"]
        transpose_label.value = (f"{t:+d}  ({tuning_code(shown_strings())})" if t
                                 else f"0  ({tuning_code(strings)})")
        header.visible = not managing
        board_area.visible = not managing
        manage_view.visible = managing

        extras = []
        if state["capo"]:
            extras.append(f"Capo {state['capo']}")
        if state["fifth_capo"]:
            extras.append(f"5th capo {state['fifth_capo']}")
        if state["fifth_start"] != DEFAULT_FIFTH_START:
            extras.append(f"5th @ {state['fifth_start']}")
        if state["tones"]:
            extras.append("♪")
        name = f"{entry_name()} {t:+d}" if t else entry_name()
        summary_text.value = "  ·  ".join([f"{name} ({tuning_code(shown_strings())})"] + extras)
        expand_icon.icon = ft.Icons.EXPAND_LESS if state["panel_open"] else ft.Icons.EXPAND_MORE

        if managing:
            manage_view.controls = manage_controls()
            page.update()
            return

        rows = build_fretboard(strings, NUM_FRETS, state["fifth_start"], t)

        def sounding(s, note):
            """What a string sounds when played 'open': with a capo, that's the note at the capo."""
            c = state["fifth_capo"] if s == 5 else state["capo"]
            return rows[c][s] if c else open_midi(note, s) + t

        header.controls = [ft.Container(width=FRET_COL_WIDTH)] + [
            header_cell(s, sounding(s, note)) for s, note in zip(STRING_ORDER, strings)
        ]

        neck = []
        for fret, row in enumerate(rows):
            neck.append(fret_row(fret, row))
            if fret == 0:
                neck.append(ft.Container(height=5, bgcolor=NUT))
        if state["transposing"]:
            # The neck sits inside the drag detector, so a vertical drag transposes instead of scrolling.
            neck_column.controls = neck
            board.controls = [neck_gesture]
        else:
            board.controls = neck
        page.update()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                expand=True,
                spacing=8,
                controls=[settings_bar, settings_panel, transpose_bar, header, board_area, manage_view],
            ),
        )
    )
    render()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
