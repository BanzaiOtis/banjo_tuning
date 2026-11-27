"""Banjo Tuning Helper: shows every note on a 5-string banjo neck for a chosen tuning.

Run on your PC with:   flet run src/main.py
"""
import asyncio
import os

import flet as ft

import settings_store
from fretboard import (
    CAPO_CHOICES,
    DEFAULT_FIFTH_START,
    FIFTH_START_CHOICES,
    MARKER_FRETS,
    NUM_FRETS,
    STRING_ORDER,
    TRANSPOSE_RANGE,
    at_capo,
    build_fretboard,
    fifth_capo_choices,
    note_name,
    open_midi,
    pretty,
    transposed_names,
    tuning_code,
    under_capo,
    uses_flats,
)
from settings_store import LABEL_CHOICES, ORIENTATION_CHOICES, PLAY_ON_CHOICES, RING_CHOICES
from theory import CHORDS, HIGHLIGHT_MODES, SCALES, highlight_set, interval_name
from tuning_store import NOTE_CHOICES, TuningStore, key_for
from version import BUILD_NUMBER, VERSION

# Sound is optional: if the flet-audio package isn't installed the app still
# runs, it just greys out the sound options.
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
CAPO_BG = "#A7B0BA"       # the capo bar
CAPO_TEXT = "#111111"
ROOT_BG = "#C0392B"       # scale/chord highlighting: the root note
ROOT_TEXT = "#FFFFFF"
MEMBER_BG = "#8C6D2C"     # scale/chord highlighting: the other notes
MEMBER_TEXT = "#FFF3D6"
PICK_COLORS = ["#E8A33D", "#4DB6AC", "#F06292", "#64B5F6", "#AED581", "#BA68C8"]  # tapped notes, in order
PICK_TEXT = "#1E1E1E"
SECTION_TEXT = "#B8A99A"
ERROR = "#FF8A80"

STRING_LABELS = {5: "5th", 4: "4th", 3: "3rd", 2: "2nd", 1: "1st"}
GROUP_LABELS = {"default": "Default tunings", "custom": "Custom tunings"}
CELL_HEIGHT = 36          # vertical neck: height of a fret row
FRET_COL_WIDTH = 36       # vertical neck: width of the fret-number column
SIDE_W = 46               # sideways neck: width of a fret column
SIDE_H = 40               # sideways neck: height of a string row
SIDE_NUM_H = 26           # sideways neck: height of the fret-number row
SIDE_LABEL_W = 54         # sideways neck: width of the string-name column
SETTINGS_HEIGHT = 380     # the settings panel scrolls if its contents are taller
STRUM_GAP = 0.09          # seconds between strings when strumming
REPO_URL = "github.com/BanzaiOtis/banjo_tuning"
CENTER = ft.Alignment(0, 0)


def main(page: ft.Page):
    page.title = "Banjo Tuning Helper"
    page.padding = 8
    page.theme_mode = ft.ThemeMode.DARK

    # On a PC, make the window phone-shaped so it previews like the real thing.
    if page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX):
        page.window.width = 420
        page.window.height = 860

    store = TuningStore()            # custom tunings + which tunings show in the menu
    saved = settings_store.load()    # everything else, remembered from last time

    # Everything the screen depends on. render() redraws from this, and saves
    # the remembered parts (settings_store.DEFAULTS keys) whenever they change.
    state = dict(saved)
    state.update(
        picks=[],               # pitch classes you've tapped, in order (each gets its own colour)
        transposing=False,      # transpose mode: dragging the neck shifts the tuning
        drag=0.0,               # drag distance not yet turned into a semitone step
        panel_open=False,       # settings panel expanded?
        view="board",           # "board", "manage" (Manage tunings) or "about"
        editing=None,           # tuning being added/edited: {"old_name", "name", "notes", "error"}
        confirm_delete=None,    # custom tuning name waiting for a second tap on delete
        message="",             # note shown on the Manage tunings screen
    )
    if not (state["tuning_key"] in {e.key for e in store.all_entries()} and store.is_visible(state["tuning_key"])):
        state["tuning_key"] = store.visible_entries()[0].key
        state["flats"] = uses_flats(store.strings_for(state["tuning_key"]))
        state["transpose"] = 0
    last_saved = {"settings": dict(saved)}
    cache = {"highlight": set(), "sounding": {}}   # worked out once per redraw

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

    def remember_settings():
        current = {k: state[k] for k in settings_store.DEFAULTS}
        if current != last_saved["settings"]:
            try:
                settings_store.save(current)
                last_saved["settings"] = current
            except OSError as err:
                print("Couldn't save settings:", err)

    def label_for(pc_or_midi):
        """Note name, or the interval above the chosen root when showing intervals."""
        if state["labels"] == "Intervals":
            return interval_name(pc_or_midi % 12, state["root"])
        return pretty(note_name(pc_or_midi, state["flats"]))

    def root_name():
        return pretty(note_name(state["root"], state["flats"]))

    def highlight_name():
        if state["highlight"] == "Scale":
            return f"{root_name()} {state['scale']}"
        if state["highlight"] == "Chord":
            return root_name() + CHORDS[state["chord"]][0]
        return ""

    # ---------- sound ----------
    players = {}       # MIDI number -> Audio player, created the first time that note is played
    play_count = {}    # MIDI number -> how many times it's been started (to cancel stale fade-outs)
    background = set() # running fade-out tasks (kept so they aren't garbage-collected)
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

    async def fade_out(midi, player, count, seconds):
        """Shorten a note: after `seconds`, fade it quickly and stop, unless it was replayed meanwhile."""
        await asyncio.sleep(seconds)
        for level in (0.6, 0.3, 0.1):
            if play_count.get(midi) != count:
                return
            player.volume = state["volume"] * level
            page.update()
            await asyncio.sleep(0.03)
        if play_count.get(midi) == count:
            await player.pause()
            player.volume = state["volume"]
            page.update()

    async def play_tone(midi):
        if fta is None or midi is None:
            return
        try:
            play_count[midi] = play_count.get(midi, 0) + 1
            player = players.get(midi)
            if player is None:
                player = fta.Audio(src=tone_source(midi), autoplay=True, volume=state["volume"])
                players[midi] = player
                page.services.append(player)  # autoplay starts it once it's loaded
                page.update()
            else:
                player.volume = state["volume"]
                page.update()
                await player.play()  # restarts from the beginning
            ring = RING_CHOICES[state["ring"]]
            if ring:
                task = asyncio.create_task(fade_out(midi, player, play_count[midi], ring))
                background.add(task)
                task.add_done_callback(background.discard)
        except Exception as err:  # keep the app running if sound fails
            print("Could not play tone:", err)

    async def strum(e):
        """Play the open strings 5th to 1st, like a strum (with any capos and transposition)."""
        for s in STRING_ORDER:
            task = asyncio.create_task(play_tone(cache["sounding"].get(s)))
            background.add(task)
            task.add_done_callback(background.discard)
            await asyncio.sleep(STRUM_GAP)

    async def on_open_string_click(e):
        await play_tone(e.control.data)

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

    def on_int_setting(key):
        def handler(e):
            state[key] = int(e.control.value)
            render()
        return handler

    def on_choice_setting(key):
        def handler(e):
            state[key] = e.control.value
            render()
        return handler

    def on_switch_setting(key):
        def handler(e):
            state[key] = e.control.value
            render()
        return handler

    def on_volume_change(e):
        state["volume"] = round(float(e.control.value), 2)
        for player in players.values():
            player.volume = state["volume"]
        page.update()
        remember_settings()

    def clear_picks(e):
        state["picks"] = []
        render()

    async def on_cell_click(e):
        midi = e.control.data
        pc = midi % 12
        if pc in state["picks"]:
            state["picks"].remove(pc)
        else:
            state["picks"].append(pc)
        render()
        if state["tones"] and state["play_on"] == "Tap":
            await play_tone(midi)

    async def on_cell_long_press(e):
        await play_tone(e.control.data)

    # ---------- transpose ----------
    def step_px():
        """Drag one fret's length = one semitone."""
        return (SIDE_W + 2) if state["orientation"] == "Sideways" else (CELL_HEIGHT + 2)

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
        # Dragging down (or right, sideways) moves notes towards higher frets = strings tuned lower.
        delta = e.primary_delta
        if delta is None and e.local_delta:
            delta = e.local_delta.x if state["orientation"] == "Sideways" else e.local_delta.y
        state["drag"] += delta or 0.0
        steps = int(state["drag"] / step_px())   # whole frets dragged so far (sign = direction)
        if steps:
            state["drag"] -= steps * step_px()
            set_transpose(state["transpose"] - steps)

    def save_transposed(e):
        t = state["transpose"]
        state.update(
            view="manage", confirm_delete=None, message="",
            editing={"old_name": None, "name": f"{entry_name()} {t:+d}" if t else entry_name(),
                     "notes": shown_strings(), "error": ""},
        )
        render()

    def toggle_settings(e):
        state["panel_open"] = not state["panel_open"]
        render()

    # ---------- other screens ----------
    def show_view(name):
        def handler(e):
            state.update(view=name, editing=None, confirm_delete=None, message="")
            render()
        return handler

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

    # ---------- settings panel controls ----------
    def dropdown(label, value, options, on_select, **kw):
        return ft.Dropdown(label=label, value=value, expand=True, on_select=on_select,
                           options=[ft.DropdownOption(key=k, text=t) for k, t in options], **kw)

    def section(title):
        return ft.Text(title, size=12, weight=ft.FontWeight.BOLD, color=SECTION_TEXT)

    tuning_dropdown = ft.Dropdown(label="Tuning", expand=True, on_select=on_tuning_select)
    capo_dropdown = dropdown("Capo", str(state["capo"]),
                             [(str(f), "None" if f == 0 else f"Fret {f}") for f in CAPO_CHOICES],
                             on_int_setting("capo"))
    fifth_capo_dropdown = ft.Dropdown(label="5th string capo", expand=True, on_select=on_int_setting("fifth_capo"))
    fifth_start_dropdown = dropdown("5th string starts at fret", str(state["fifth_start"]),
                                    [(str(f), str(f)) for f in FIFTH_START_CHOICES], on_fifth_start_select)
    flats_switch = ft.Switch(label="Flats", on_change=on_switch_setting("flats"))
    transpose_switch = ft.Switch(label="Transpose mode", on_change=on_transposing_change)

    highlight_dropdown = dropdown("Highlight", state["highlight"], [(m, m) for m in HIGHLIGHT_MODES],
                                  on_choice_setting("highlight"))
    root_dropdown = ft.Dropdown(label="Root", expand=True, on_select=on_int_setting("root"))
    scale_dropdown = dropdown("Scale", state["scale"], [(s, s) for s in SCALES], on_choice_setting("scale"))
    chord_dropdown = dropdown("Chord", state["chord"], [(c, c) for c in CHORDS], on_choice_setting("chord"))
    labels_dropdown = dropdown("Show", state["labels"],
                               [("Notes", "Note names"), ("Intervals", "Intervals from root")],
                               on_choice_setting("labels"))
    orientation_dropdown = dropdown("Neck", state["orientation"],
                                    [(o, o) for o in ORIENTATION_CHOICES], on_choice_setting("orientation"))

    tones_switch = ft.Switch(
        label="Play notes when tapped" if fta else "Sound (install flet-audio)",
        disabled=fta is None,
        on_change=on_switch_setting("tones"),
    )
    play_on_dropdown = dropdown("Play on", state["play_on"], [(p, p) for p in PLAY_ON_CHOICES],
                                on_choice_setting("play_on"), disabled=fta is None)
    ring_dropdown = dropdown("Ring length", state["ring"], [(r, r) for r in RING_CHOICES],
                             on_choice_setting("ring"), disabled=fta is None)
    volume_slider = ft.Slider(min=0, max=1, divisions=10, value=state["volume"], label="{value}",
                              expand=True, disabled=fta is None, on_change_end=on_volume_change)

    settings_panel = ft.Container(
        visible=False,
        height=SETTINGS_HEIGHT,
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
            controls=[
                section("TUNING"),
                ft.Row([tuning_dropdown]),
                ft.Row([capo_dropdown, fifth_capo_dropdown]),
                ft.Row([fifth_start_dropdown]),
                ft.Row([flats_switch, transpose_switch], wrap=True),
                section("HIGHLIGHT & LABELS"),
                ft.Row([highlight_dropdown, root_dropdown]),
                ft.Row([scale_dropdown, chord_dropdown]),
                ft.Row([labels_dropdown, orientation_dropdown]),
                section("SOUND"),
                tones_switch,
                ft.Row([play_on_dropdown, ring_dropdown]),
                ft.Row([ft.Icon(ft.Icons.VOLUME_UP, size=20), volume_slider]),
                ft.Text("Tap a string name to hear it, or ♪ to strum the open strings.", size=12,
                        color=SECTION_TEXT),
                ft.Row([
                    ft.TextButton("Manage tunings", icon=ft.Icons.EDIT, on_click=show_view("manage")),
                    ft.TextButton("About", icon=ft.Icons.INFO_OUTLINE, on_click=show_view("about")),
                ], wrap=True),
            ],
        ),
    )

    # ---------- always-visible bars ----------
    summary_text = ft.Text(size=15, weight=ft.FontWeight.BOLD, expand=True, max_lines=1,
                           overflow=ft.TextOverflow.ELLIPSIS)
    expand_icon = ft.Icon(ft.Icons.EXPAND_MORE)
    clear_button = ft.IconButton(icon=ft.Icons.CLEAR, tooltip="Clear tapped notes", visible=False,
                                 on_click=clear_picks)
    settings_bar = ft.Container(
        padding=ft.Padding(12, 4, 8, 4),
        bgcolor=WOOD_DARK,
        border_radius=8,
        ink=True,
        on_click=toggle_settings,
        content=ft.Row([ft.Icon(ft.Icons.TUNE, size=20), summary_text, clear_button, expand_icon]),
    )
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

    # ---------- the neck: vertical ----------
    header = ft.Row(spacing=2)
    board = ft.ListView(expand=True, spacing=2)
    # Used in transpose mode. Created once and reused, so a swipe in progress
    # isn't cut off when the notes are redrawn after each semitone step.
    neck_column = ft.Column(spacing=2)
    neck_gesture = ft.GestureDetector(
        content=neck_column,
        on_vertical_drag_start=on_drag_start,
        on_vertical_drag_update=on_drag_update,
    )
    board_area = ft.Container(expand=True, bgcolor=FRET_WIRE, content=board)

    # ---------- the neck: sideways (1st string on top, like tab) ----------
    side_labels = ft.Column(spacing=2, width=SIDE_LABEL_W)
    side_scroll = ft.Row(scroll=ft.ScrollMode.AUTO, vertical_alignment=ft.CrossAxisAlignment.START)
    side_grid = ft.Column(spacing=2)               # transpose mode only, reused like neck_column
    side_gesture = ft.GestureDetector(
        content=ft.Container(bgcolor=FRET_WIRE, content=side_grid),
        on_horizontal_drag_start=on_drag_start,
        on_horizontal_drag_update=on_drag_update,
    )
    side_area = ft.Row(
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=2,
        controls=[side_labels, ft.Container(expand=True, content=side_scroll)],
    )

    manage_view = ft.ListView(expand=True, spacing=6, visible=False)
    about_view = ft.ListView(expand=True, spacing=10, visible=False)

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

    def note_cell(midi, fret, string_no, width=None, height=CELL_HEIGHT):
        size = {"width": width, "height": height} if width else {"expand": 1, "height": height}
        capo, fifth_capo = state["capo"], state["fifth_capo"]
        if midi is None:   # no 5th string here
            return ft.Container(bgcolor=WOOD_DARK, **size)
        if under_capo(string_no, fret, capo, fifth_capo):
            # behind a capo: shown greyed out, and can't be tapped
            return ft.Container(
                alignment=CENTER, bgcolor=UNDER_CAPO, **size,
                content=ft.Text(label_for(midi), size=15, color=UNDER_CAPO_TEXT),
            )
        pc = midi % 12
        picked = pc in state["picks"]
        capo_here = at_capo(string_no, fret, capo, fifth_capo)
        if picked:
            bg = PICK_COLORS[state["picks"].index(pc) % len(PICK_COLORS)]
            color = PICK_TEXT
        elif pc in cache["highlight"]:
            bg, color = (ROOT_BG, ROOT_TEXT) if pc == state["root"] else (MEMBER_BG, MEMBER_TEXT)
        elif capo_here:
            bg, color = CAPO_BG, CAPO_TEXT
        else:
            bg = WOOD_DARK if fret == 0 else WOOD
            color = MARKER if fret in MARKER_FRETS else TEXT
        bold = picked or capo_here or fret in MARKER_FRETS or (pc in cache["highlight"] and pc == state["root"])
        long_press = state["tones"] and state["play_on"] == "Long-press"
        return ft.Container(
            alignment=CENTER,
            bgcolor=bg,
            border_radius=4 if picked else 0,
            ink=True,
            data=midi,
            on_click=on_cell_click,
            on_long_press=on_cell_long_press if long_press else None,
            content=ft.Text(label_for(midi), size=15, color=color,
                            weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL),
            **size,
        )

    def fret_label(fret, width=None, height=CELL_HEIGHT):
        is_capo = fret > 0 and fret in (state["capo"], state["fifth_capo"])
        size = {"width": width or FRET_COL_WIDTH, "height": height}
        return ft.Container(
            alignment=CENTER,
            bgcolor=CAPO_BG if is_capo else WOOD_DARK,
            content=ft.Text(
                "Open" if fret == 0 else str(fret),
                size=11 if fret == 0 else 13,
                color=CAPO_TEXT if is_capo else (MARKER if fret in MARKER_FRETS else TEXT),
                weight=ft.FontWeight.BOLD if (is_capo or fret in MARKER_FRETS) else ft.FontWeight.NORMAL,
            ),
            **size,
        )

    def strum_button(width, height):
        return ft.Container(
            width=width, height=height, alignment=CENTER, ink=fta is not None,
            on_click=strum if fta else None,
            content=ft.Icon(ft.Icons.MUSIC_NOTE, size=20, color=MARKER if fta else UNDER_CAPO_TEXT),
        )

    def open_string_label(string_no, **size):
        midi = cache["sounding"][string_no]
        return ft.Container(
            alignment=CENTER, ink=fta is not None, data=midi,
            on_click=on_open_string_click if fta else None,
            content=ft.Column(
                spacing=0,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(STRING_LABELS[string_no], size=11),
                    ft.Text(label_for(midi), size=16, weight=ft.FontWeight.BOLD),
                ],
            ),
            **size,
        )

    def draw_vertical(rows):
        header.controls = [strum_button(FRET_COL_WIDTH, 40)] + [
            open_string_label(s, expand=1) for s in STRING_ORDER
        ]
        neck = []
        for fret, row in enumerate(rows):
            neck.append(ft.Row(spacing=2, controls=[fret_label(fret)] +
                               [note_cell(row[s], fret, s) for s in STRING_ORDER]))
            if fret == 0:
                neck.append(ft.Container(height=5, bgcolor=NUT))
        if state["transposing"]:
            # The neck sits inside the drag detector, so a vertical drag transposes instead of scrolling.
            neck_column.controls = neck
            board.controls = [neck_gesture]
        else:
            board.controls = neck

    def draw_sideways(rows):
        nut = lambda h: ft.Container(width=5, height=h, bgcolor=NUT)  # noqa: E731
        side_labels.controls = [strum_button(SIDE_LABEL_W, SIDE_NUM_H)] + [
            open_string_label(s, width=SIDE_LABEL_W, height=SIDE_H) for s in reversed(STRING_ORDER)
        ]
        number_row = [fret_label(0, SIDE_W, SIDE_NUM_H), nut(SIDE_NUM_H)] + [
            fret_label(f, SIDE_W, SIDE_NUM_H) for f in range(1, NUM_FRETS + 1)
        ]
        grid = [ft.Row(spacing=2, controls=number_row)]
        for s in reversed(STRING_ORDER):   # 1st string on top
            cells = [note_cell(rows[0][s], 0, s, SIDE_W, SIDE_H), nut(SIDE_H)] + [
                note_cell(rows[f][s], f, s, SIDE_W, SIDE_H) for f in range(1, NUM_FRETS + 1)
            ]
            grid.append(ft.Row(spacing=2, controls=cells))
        if state["transposing"]:
            # A sideways drag transposes instead of scrolling.
            side_grid.controls = grid
            side_scroll.controls = [side_gesture]
        else:
            side_scroll.controls = [ft.Container(bgcolor=FRET_WIRE, content=ft.Column(grid, spacing=2))]

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
                ft.FilledButton("Done", on_click=show_view("board")),
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

    def about_controls():
        return [
            ft.Row([
                ft.Text("About", size=18, weight=ft.FontWeight.BOLD, expand=True),
                ft.FilledButton("Done", on_click=show_view("board")),
            ]),
            ft.Text("Banjo Tuning Helper", size=22, weight=ft.FontWeight.BOLD),
            ft.Text(f"Version {VERSION}  (build {BUILD_NUMBER})", size=15),
            ft.Text("Shows every note on a 5-string banjo neck in any tuning, with capos, "
                    "transposing, scales, chords and sound."),
            ft.Divider(),
            ft.Text("Sounds are synthesized plucked-string tones tuned to A = 440 Hz.", size=13),
            ft.Text("Built in Python with Flet.", size=13),
            ft.Text(f"Source code: {REPO_URL}", size=13, selectable=True),
        ]

    # ---------- draw everything from `state` ----------
    def render():
        # The current tuning may have been hidden or deleted: fall back to the first one in the menu.
        visible_keys = [e.key for e in store.visible_entries()]
        if state["tuning_key"] not in visible_keys:
            state["tuning_key"] = visible_keys[0]
            state["flats"] = uses_flats(current_strings())
            state["transpose"] = 0
        remember_settings()

        strings = current_strings()
        t = state["transpose"]
        view = state["view"]
        on_board = view == "board"
        sideways = state["orientation"] == "Sideways"

        # Settings controls mirror `state`.
        tuning_dropdown.options = tuning_options()
        tuning_dropdown.value = state["tuning_key"]
        fifth_capo_dropdown.options = [
            ft.DropdownOption(key=str(f), text="None" if f == 0 else f"Fret {f}")
            for f in fifth_capo_choices(state["fifth_start"])
        ]
        fifth_capo_dropdown.value = str(state["fifth_capo"])
        flats_switch.value = state["flats"]
        transpose_switch.value = state["transposing"]
        tones_switch.value = state["tones"]
        root_dropdown.options = [ft.DropdownOption(key=str(pc), text=pretty(note_name(pc, state["flats"])))
                                 for pc in range(12)]
        root_dropdown.value = str(state["root"])
        root_dropdown.disabled = state["highlight"] == "None" and state["labels"] == "Notes"
        scale_dropdown.visible = state["highlight"] != "Chord"
        scale_dropdown.disabled = state["highlight"] == "None"
        chord_dropdown.visible = state["highlight"] == "Chord"

        settings_bar.visible = on_board
        settings_panel.visible = state["panel_open"] and on_board
        transpose_bar.visible = state["transposing"] and on_board
        transpose_label.value = f"{t:+d}  ({tuning_code(shown_strings())})" if t else f"0  ({tuning_code(strings)})"
        header.visible = on_board and not sideways
        board_area.visible = on_board and not sideways
        side_area.visible = on_board and sideways
        manage_view.visible = view == "manage"
        about_view.visible = view == "about"
        clear_button.visible = bool(state["picks"])

        extras = []
        if state["capo"]:
            extras.append(f"Capo {state['capo']}")
        if state["fifth_capo"]:
            extras.append(f"5th capo {state['fifth_capo']}")
        if state["fifth_start"] != DEFAULT_FIFTH_START:
            extras.append(f"5th @ {state['fifth_start']}")
        if state["highlight"] != "None":
            extras.append(highlight_name())
        elif state["labels"] == "Intervals":
            extras.append(f"Intervals from {root_name()}")
        if state["tones"]:
            extras.append("♪")
        name = f"{entry_name()} {t:+d}" if t else entry_name()
        summary_text.value = "  ·  ".join([f"{name} ({tuning_code(shown_strings())})"] + extras)
        expand_icon.icon = ft.Icons.EXPAND_LESS if state["panel_open"] else ft.Icons.EXPAND_MORE

        if view == "manage":
            manage_view.controls = manage_controls()
        elif view == "about":
            about_view.controls = about_controls()
        else:
            rows = build_fretboard(strings, NUM_FRETS, state["fifth_start"], t)
            cache["highlight"] = highlight_set(state["highlight"], state["root"], state["scale"], state["chord"])

            def sounding(s, note):
                """What a string sounds when played 'open': with a capo, that's the note at the capo."""
                c = state["fifth_capo"] if s == 5 else state["capo"]
                return rows[c][s] if c else open_midi(note, s) + t

            cache["sounding"] = {s: sounding(s, note) for s, note in zip(STRING_ORDER, strings)}
            if sideways:
                draw_sideways(rows)
            else:
                draw_vertical(rows)
        page.update()

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Column(
                expand=True,
                spacing=8,
                controls=[settings_bar, settings_panel, transpose_bar, header, board_area, side_area,
                          manage_view, about_view],
            ),
        )
    )
    render()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
