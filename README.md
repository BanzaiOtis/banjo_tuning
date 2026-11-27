# Banjo Tuning Helper

Shows the name of every note on a 5-string banjo neck (open to fret 25) for the tuning you pick.
Tap any note to highlight everywhere else it appears.

## Project layout

```
banjo_tuning/
  pyproject.toml        project settings (used later to build the Android app)
  src/
    main.py             the screen: dropdown, switch, fretboard grid
    fretboard.py        the music logic (note names, which note is at which fret)
    tunings.py          the built-in (default) tunings
    tuning_store.py     saves/loads your custom tunings and which tunings show in the menu
    assets/tones/       one short plucked-string sound per pitch (n48.wav = MIDI note 48 = C3)
  tools/
    make_tones.py       regenerates the sound files; tweak its settings to change the sound
  tests/
    test_fretboard.py   checks the music logic
    test_tuning_store.py checks saving/loading tunings
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

Check the music logic: `python tests/test_fretboard.py`

## How the 5th string is shown

The short 5th string usually begins at the 5th fret (you can change this in the app), so its cells below that fret are blank.
Its open note appears in the row for the fret where it starts, and it goes up a semitone per fret from there,
matching how banjo tab numbers the 5th string.

## Tones

Turn on **Tones** and tapping a note plays it at the pitch it really sounds on the banjo
(Open G is g4 D3 G3 B3 D4; a retuned string uses the nearest pitch with its new note name,
so Drop C's 4th string is C3). Sound needs the `flet-audio` package. Without it the switch is greyed out.

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
1. Bump both numbers in `pyproject.toml`, commit and push (or ask Claude to).
2. Pull in GitHub Desktop, then build: `flet build apk`
3. Install and test the APK on your phone.
4. On GitHub: **Releases → Draft a new release**, create tag `vX.Y.Z` on `main`, describe the changes,
   attach the APK (renamed e.g. `banjo_tuning-0.2.0.apk`), and publish.
