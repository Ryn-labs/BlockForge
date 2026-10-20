"""Local gallery: every build lives in data/builds/<id>/ (meta.json, code.py, blocks.json)."""
import json
import os
import shutil
import threading
import re
import time
import uuid

from . import exporters

ROOT = os.path.dirname(os.path.abspath(__file__))
# Per-user data folder, shared by the installed app, the source checkout and the Claude Code link.
DATA = os.environ.get("BLOCKFORGE_DATA") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "BlockForge")
BUILDS = os.path.join(DATA, "builds")
SETTINGS = os.path.join(DATA, "settings.json")


def _migrate_old_data():
    """Builds made before the app was installable lived in blockforge/data/."""
    old = os.path.join(ROOT, "data")
    if os.path.isdir(os.path.join(old, "builds")) and not os.path.isdir(BUILDS):
        import shutil
        shutil.copytree(os.path.join(old, "builds"), BUILDS)
        if os.path.isfile(os.path.join(old, "settings.json")):
            shutil.copy(os.path.join(old, "settings.json"), SETTINGS)


os.makedirs(DATA, exist_ok=True)
_migrate_old_data()
os.makedirs(BUILDS, exist_ok=True)

DEFAULT_SETTINGS = {
    "engine": "claude_code", "api_key": "", "model": "claude-opus-5-5", "author": "",
    "research": True, "research_sites": None,             # None = the built-in list in prompts.DEFAULT_SITES
    "default_size": "medium", "default_palette": "auto",
    "custom_palettes": [],                                 # [{"name": ..., "description": ...}]
    "ui": {},                                              # appearance choices made in Settings > Appearance
    "guide": {},
    "eleven": {},                                          # ElevenLabs voice: {"api_key", "voice_id", "voice_name", "model"}
    "providers": {},
    "modpacks": [],                                         # scanned packs: [{"id", "name", "path"}]
    "active_pack": None, "use_mods": True, "target_version": "1.21.1",
    "learn_examples": True, "learn_log": True,              # local learning loop (Settings -> Learning)                                       # other AIs: {id: {"api_key", "base_url", "model", "models"}}                                           # the guide character (name, voice, colours...)
}
USAGE_LOG = os.path.join(DATA, "usage.jsonl")


_settings_lock = threading.RLock()
MERGE_KEYS = ("eleven", "providers")                    # nested settings: updates add to them, never drop other keys


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        raise ValueError("settings must be an object")
    return d


def _read_stored():
    """What's on disk: the main file, or the backup if the main file is damaged. None if there are no settings yet.
    Raises if settings exist but none can be read (so we never overwrite them with blanks)."""
    problem = None
    for path in (SETTINGS, SETTINGS + ".bak"):
        if not os.path.isfile(path):
            continue
        try:
            return _read_json(path)
        except (OSError, ValueError) as e:
            problem = e
    if problem:
        raise OSError(f"settings file is unreadable: {problem}")
    return None


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    with _settings_lock:
        try:
            stored = _read_stored()
        except OSError:
            stored = None
    if stored:
        s.update(stored)
    return s


def save_settings(new):
    with _settings_lock:
        stored = _read_stored()                            # raises rather than losing keys we can't read
        s = dict(DEFAULT_SETTINGS)
        s.update(stored or {})
        for k, v in new.items():
            if k not in DEFAULT_SETTINGS:
                continue
            if k in MERGE_KEYS and isinstance(v, dict) and isinstance(s.get(k), dict):
                s[k] = {**s[k], **v}
            else:
                s[k] = v
        data = json.dumps(s, indent=2)
        tmp = SETTINGS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if os.path.isfile(SETTINGS):
            try:
                shutil.copyfile(SETTINGS, SETTINGS + ".bak")   # last known-good copy
            except OSError:
                pass
        os.replace(tmp, SETTINGS)                          # atomic: readers see the old file or the new one, never half
        return s


def _dir(bid):
    if not re.fullmatch(r"[a-z0-9_-]{4,64}", bid or ""):
        raise KeyError(bid)
    return os.path.join(BUILDS, bid)


def slug(text):
    s = re.sub(r"[^A-Za-z0-9]+", "_", text or "build").strip("_")
    return s[:48] or "build"


def save_build(blocks, title, prompt="", code=None, source="app", parent=None, model=None,
               description="", image_bytes=None, image_ext=None, usage=None, references=None, researched=False,
               redstone=False, warnings=None, fixes=None, data_version=None, modpack=None):
    bid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = _dir(bid)
    os.makedirs(d)
    data = exporters.to_dict(blocks)
    if data_version:
        data["data_version"] = data_version
    counts = {}
    for st in blocks.values():
        n = st.split("[", 1)[0].replace("minecraft:", "")
        counts[n] = counts.get(n, 0) + 1
    meta = {
        "id": bid, "title": title or "Untitled build", "prompt": prompt, "description": description,
        "created": time.time(), "source": source, "parent": parent, "model": model,
        "size": data["size"], "block_count": len(blocks), "has_code": bool(code),
        "materials": sorted(counts.items(), key=lambda kv: -kv[1]),
        "has_image": bool(image_bytes),
        "usage": usage, "references": references or [], "researched": researched,
        "redstone": redstone, "warnings": warnings or [], "fixes": fixes or [], "modpack": modpack,
    }
    with open(os.path.join(d, "blocks.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    if code:
        with open(os.path.join(d, "code.py"), "w", encoding="utf-8") as f:
            f.write(code)
    if image_bytes:
        meta["image"] = "reference" + (image_ext or ".png")
        with open(os.path.join(d, meta["image"]), "wb") as f:
            f.write(image_bytes)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return meta


def list_builds():
    out = []
    for bid in os.listdir(BUILDS):
        try:
            with open(os.path.join(BUILDS, bid, "meta.json"), encoding="utf-8") as f:
                m = json.load(f)
            m.pop("materials", None)
            out.append(m)
        except (OSError, ValueError):
            continue
    out.sort(key=lambda m: -m.get("created", 0))
    return out


def get_meta(bid):
    with open(os.path.join(_dir(bid), "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def update_meta(bid, **kw):
    m = get_meta(bid)
    m.update(kw)
    with open(os.path.join(_dir(bid), "meta.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1)
    return m


def get_blocks_raw(bid):
    with open(os.path.join(_dir(bid), "blocks.json"), "rb") as f:
        return f.read()


def get_blocks(bid):
    return json.loads(get_blocks_raw(bid))


def get_code(bid):
    try:
        with open(os.path.join(_dir(bid), "code.py"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def file_path(bid, name):
    p = os.path.join(_dir(bid), os.path.basename(name))
    if not os.path.isfile(p):
        raise KeyError(name)
    return p


TRASH = os.path.join(DATA, "trash")


def delete_build(bid):
    """Moves the build to the trash folder (DATA/trash) so a mistaken delete can be undone by moving it back."""
    src = _dir(bid)
    if not os.path.isdir(src):
        raise KeyError(bid)
    os.makedirs(TRASH, exist_ok=True)
    dest = os.path.join(TRASH, os.path.basename(src))
    if os.path.exists(dest):
        dest += "-" + uuid.uuid4().hex[:4]
    shutil.move(src, dest)
    os.utime(dest, None)                                     # a move keeps the old time; the 30 days start now
    cutoff = time.time() - 30 * 86400                        # empty out things trashed over 30 days ago
    for d in os.listdir(TRASH):
        p = os.path.join(TRASH, d)
        try:
            if os.path.isdir(p) and os.path.getmtime(p) < cutoff:
                shutil.rmtree(p)
        except OSError:
            pass


def export_path(bid, fmt):
    m = get_meta(bid)
    ext = exporters.FORMATS[fmt][1]
    out_dir = os.path.join(_dir(bid), "exports")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, slug(m["title"]) + ext)
    if not os.path.exists(path):
        exporters.export(get_blocks(bid), fmt, path, m["title"], m.get("prompt", ""))
    return path


# ------------------------------------------------------------------ Claude usage log
def log_usage(rec):
    with open(USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def usage_summary(limit=100):
    rows = []
    try:
        with open(USAGE_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    now = time.time()
    day0 = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))

    def total(rs):
        keys = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "total_tokens",
                "web_searches", "web_fetches", "cost_usd", "seconds")
        t = {k: sum(r.get(k) or 0 for r in rs) for k in keys}
        t["cost_usd"] = round(t["cost_usd"], 4)
        t["builds"] = sum(1 for r in rs if r.get("status") == "done")
        t["failed"] = sum(1 for r in rs if r.get("status") != "done")
        return t
    by_model = {}
    for r in rows:
        by_model.setdefault(r.get("model") or "?", []).append(r)
    return {
        "today": total([r for r in rows if r.get("time", 0) >= day0]),
        "week": total([r for r in rows if r.get("time", 0) >= now - 7 * 86400]),
        "all": total(rows),
        "by_model": {m: total(rs) for m, rs in by_model.items()},
        "recent": list(reversed(rows))[:limit],
    }
