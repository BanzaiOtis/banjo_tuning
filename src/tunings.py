"""The tunings the app offers. Edit this file to add, rename or correct tunings.

Each entry lists the open notes from the 5th (short drone) string to the 1st string.
Write sharps with # and flats with b, e.g. "F#" or "Bb".

Names for some tunings vary between players and sources:
  - Old G: also seen as gDGBE (that one is listed here as "Standard guitar").
  - Open D: some players tune the 5th string up to A instead of down to F#.
  - C minor: an open C-minor chord; check it against your own source.
"""

TUNINGS = {
    "Open G":          ("G", "D", "G", "B", "D"),
    "G modal":         ("G", "D", "G", "C", "D"),   # aka Sawmill / mountain minor
    "Double C":        ("G", "C", "G", "C", "D"),
    "Drop C":          ("G", "C", "G", "B", "D"),   # aka C tuning
    "Open D":          ("F#", "D", "F#", "A", "D"),
    "G/D":             ("G", "D", "G", "A", "D"),
    "Old G":           ("G", "D", "G", "D", "E"),
    "Open C":          ("G", "C", "G", "C", "E"),
    "G minor":         ("G", "D", "G", "Bb", "D"),
    "C minor":         ("G", "C", "G", "C", "Eb"),
    "Standard guitar": ("G", "D", "G", "B", "E"),   # top four strings like a guitar
}

DEFAULT_TUNING = "Open G"
