"""Catalog of Piper voices Flint can use. Joe ships with the app; the rest download on demand (about 60 MB each)
from the official piper-voices repository on Hugging Face. Only voices that are public domain, CC0, Apache-2.0
or CC-BY are listed, so they're fine to use and share."""
import os
import urllib.request

from . import store

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED_DIR = os.path.join(HERE, "voice")
USER_DIR = os.path.join(store.DATA, "voices")
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"

# id: (label, path in the repo, file stem, licence, bundled)
CATALOG = {
    "joe": ("Joe · US male, friendly", "en/en_US/joe/medium", "en_US-joe-medium", "CC0", True),
    "bryce": ("Bryce · US male, warm", "en/en_US/bryce/medium", "en_US-bryce-medium", "Public domain", False),
    "norman": ("Norman · US male, deep", "en/en_US/norman/medium", "en_US-norman-medium", "Public domain", False),
    "john": ("John · US male, calm", "en/en_US/john/medium", "en_US-john-medium", "Public domain", False),
    "kristin": ("Kristin · US female, bright", "en/en_US/kristin/medium", "en_US-kristin-medium", "Public domain", False),
    "ljspeech": ("Linda · US female, clear", "en/en_US/ljspeech/medium", "en_US-ljspeech-medium", "Public domain", False),
    "kathleen": ("Kathleen · US female, soft", "en/en_US/kathleen/low", "en_US-kathleen-low", "CC0", False),
    "sam": ("Sam · US, easygoing", "en/en_US/sam/medium", "en_US-sam-medium", "Apache 2.0", False),
    "alba": ("Alba · Scottish female", "en/en_GB/alba/medium", "en_GB-alba-medium", "CC BY 4.0 (Alba voice, Edinburgh CSTR)", False),
}


def path(vid):
    """Full path of an installed voice's .onnx file, or None."""
    entry = CATALOG.get(vid)
    if not entry:
        return None
    for folder in ((BUNDLED_DIR, USER_DIR) if entry[4] else (USER_DIR, BUNDLED_DIR)):
        p = os.path.join(folder, entry[2] + ".onnx")
        if os.path.isfile(p) and os.path.isfile(p + ".json"):
            return p
    return None


def installed():
    return {vid: e[0] for vid, e in CATALOG.items() if path(vid)}


def catalog_info():
    return [{"id": vid, "label": e[0], "license": e[3], "bundled": e[4], "installed": bool(path(vid)), "size_mb": 60}
            for vid, e in CATALOG.items()]


def download(vid, log=print):
    entry = CATALOG.get(vid)
    if not entry:
        raise ValueError("Unknown voice")
    if path(vid):
        return
    os.makedirs(USER_DIR, exist_ok=True)
    base = HF + entry[1] + "/" + entry[2] + ".onnx"
    for suffix in (".json", ""):                       # the small config first, then the big model
        dest = os.path.join(USER_DIR, entry[2] + ".onnx" + suffix)
        req = urllib.request.Request(base + suffix, headers={"User-Agent": "BlockForge"})
        log(f"Downloading {entry[0].split(' · ')[0]}'s voice...")
        with urllib.request.urlopen(req, timeout=60) as r, open(dest + ".part", "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done, last = 0, -10
            while True:
                chunk = r.read(1 << 18)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and suffix == "":
                    pct = int(100 * done / total)
                    if pct >= last + 10:
                        last = pct - pct % 10
                        log(f"Downloading... {last}%")
        if suffix == "" and os.path.getsize(dest + ".part") < 5_000_000:
            os.remove(dest + ".part")
            raise RuntimeError("The voice download was incomplete. Try again.")
        os.replace(dest + ".part", dest)
    log("Voice installed.")
