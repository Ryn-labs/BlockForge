"""Build lessons and style sheets for the building AI. Plain text files next to this module."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STYLES_DIR = os.path.join(HERE, "styles")
LESSONS_FILE = os.path.join(HERE, "lessons.md")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def top(n=40):
    """The first n lesson lines (without the bullet), in file order."""
    lines = [ln[2:].strip() for ln in _read(LESSONS_FILE).splitlines() if ln.startswith("- ")]
    return lines[:max(0, int(n))]


def styles():
    """Names of the available style sheets, sorted."""
    try:
        return sorted(f[:-3] for f in os.listdir(STYLES_DIR) if f.endswith(".md"))
    except OSError:
        return []


def for_style(name):
    """The style sheet text for a style name (case and spaces ignored), or '' if unknown."""
    key = str(name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key not in styles():
        return ""
    return _read(os.path.join(STYLES_DIR, key + ".md"))
