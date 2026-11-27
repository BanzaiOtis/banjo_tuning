"""Checks that src/version.py matches pyproject.toml. Run with:  python tests/test_version.py"""
import os
import sys
import tomllib

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from version import BUILD_NUMBER, VERSION  # noqa: E402


def test_version_matches_pyproject():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        project = tomllib.load(f)
    assert project["project"]["version"] == VERSION, "update src/version.py VERSION"
    assert project["tool"]["flet"]["build_number"] == BUILD_NUMBER, "update src/version.py BUILD_NUMBER"


if __name__ == "__main__":
    test_version_matches_pyproject()
    print("ok  test_version_matches_pyproject")
    print("All checks passed.")
