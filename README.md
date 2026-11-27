# Banjo Tuning Helper

Shows the name of every note on a 5-string banjo neck (open to fret 25) for the tuning you pick.
Tap notes to highlight them everywhere they appear, light up a scale or chord, and hear any note
at its real pitch.

## Project layout

```
banjo_tuning/
  pyproject.toml        project settings (used later to build the Android app)
  src/
    main.py             the screens: settings, fretboard (vertical or sideways), Manage tunings, About
    fretboard.py        the music logic (note names, which note is at which fret)
    theory.py           scales, chords and interval names
    tunings.py          the built-in (default) tunings
    tuning_store.py     saves/loads your custom tunings and which tunings show in the menu
    settings_store.py   remembers your settings between launches
    version.py          version shown on the About screen (must match pyproject.toml)
    assets/tones/       one short plucked-string sound per pitch (n48.wav = MIDI note 48 = C3)
  tools/
    make_tones.py       regenerates the sound files; tweak its settings to change the sound
  tests/                checks for the logic modules (GitHub runs them on every push)
  .github/workflows/    the GitHub "Tests" job
```

## One-time setup (Anaconda Prompt)

Open **Anaconda Prompt** from the Start menu and run:

```
conda create -n banjo python=3.12 -y
conda activate banjo
pip install "flet[all]" flet-audio
```

The environment lives in your Anaconda folder, not in Google Drive, which is what you want.
Google Drive would try to sync thousands of library files.

## Getting the latest changes

Changes are committed to GitHub (github.com/BanzaiOtis/banjo_tuning). Before running or building,
open **GitHub Desktop** and click **Fetch origin**, then **Pull origin**. If you edit files yourself,
commit and push them before asking for more changes, so the two copies don't conflict.

## Every time you work on it

```
conda activate banjo
cd /d D:\dev\banjo_tuning
flet run src/main.py
```

A phone-shaped window opens. Leave it open: **saving a change to a .py file reloads the app automatically.**

To preview on your phone instead, run `flet run --android src/main.py` and scan the QR code with the
Flet app (phone and PC on the same Wi-Fi).

Check the logic: run any file in `tests/`, e.g. `python tests/test_fretboard.py`.
GitHub also runs all of them after every push: see the ✓ / ✗ next to each commit, or the **Actions** tab.

## How the 5th string is shown

The short 5th string usually begins at the 5th fret (you can change this in the app), so its cells below that fret are blank.
Its open note appears in the row for the fret where it starts, and it goes up a semitone per fret from there,
matching how banjo tab numbers the 5th string.

## Sound

- **Tap a string name** (above the neck, or left of it when sideways) to hear that open string,
  and tap **♪** to strum all five. Handy for tuning by ear. These work whether or not note sounds are on.
- Turn on **Play notes when tapped** to hear each note you tap, at the pitch it really sounds on the banjo
  (Open G is g4 D3 G3 B3 D4; a retuned string uses the nearest pitch with its new note name,
  so Drop C's 4th string is C3).
- **Play on: Long-press** makes a normal tap only highlight; press and hold to hear the note.
- **Ring length** (Short / Medium / Full) and **volume** are in the Sound section of the settings.

Sound needs the `flet-audio` package. Without it the sound options are greyed out.

## Highlighting

- **Tap notes** to highlight them everywhere on the neck, each in its own colour (good for building a chord shape).
  Tap again to remove one, or ✕ in the top bar to clear them all.
- **Highlight: Scale / Chord** with a **Root** lights up every note of, say, G Mixolydian or D7:
  the root in red, the other notes in gold.
- **Show: Intervals from root** replaces note names with their role relative to the root (1, ♭3, 5, ♭7...).

## Other settings

- **Neck: Sideways** lays the neck horizontally with the 1st string on top, like tab; scroll left and right.
  Best with the phone turned to landscape.
- Your settings are remembered between launches (in `settings.json` next to `tunings.json`).
- **About** (bottom of the settings) shows the version and build number.

## Capo and custom tunings

- **Capo** (in the settings panel): the capo shows as a silver bar across the 4th-1st strings.
  Notes behind it are greyed out (and can't be tapped), and the string headings show the notes the open strings now sound.
  The 5th string has its own **5th string capo** setting, which works the same way.
- **Manage tunings** (button in the settings panel): tick which tunings appear in the menu
  (or use Select all / Deselect all),
  and add, edit or delete your own. They're saved on the device in `tunings.json` in the app's data folder
  (on your PC during `flet run`: `src/.flet/storage/data/`).

## Transpose

Turn on **Transpose mode** in the settings panel, then drag the fretboard up or down: each fret's worth
of drag moves every string up or down a semitone, keeping the intervals (or use the − / + buttons).
The bar shows the shift and the resulting tuning; ⟲ resets it and 💾 saves it as a custom tuning.
While the mode is on, dragging transposes instead of scrolling; turn it off to scroll again
(the transposition stays applied).

## Releasing a new version

Each release has two numbers in `pyproject.toml`:

- `version` (e.g. 0.2.0) is what users see. Raise the **patch** (0.2.**1**) for fixes,
  the **minor** (0.**3**.0) for new features, and the **major** (**1**.0.0) for the first Play Store release.
- `build_number` is Android's internal version code. Add 1 every release, and never reuse or lower it.

Steps:
1. Bump both numbers in `pyproject.toml` **and** `src/version.py` (the About screen reads that one;
   the tests fail if they don't match), commit and push (or ask Claude to).
2. Pull in GitHub Desktop, then build: `flet build apk`
3. Install and test the APK on your phone.
4. On GitHub: **Releases → Draft a new release**, create tag `vX.Y.Z` on `main`, describe the changes,
   attach the APK (renamed e.g. `banjo_tuning-0.2.0.apk`), and publish.
