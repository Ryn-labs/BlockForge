"""Local gallery: every build lives in data/builds/<id>/ (meta.json, code.py, blocks.json)."""
import json
import os
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
    "providers": {},                                       # other AIs: {id: {"api_key", "base_url", "model", "models"}}                                           # the guide character (name, voice, colours...)
}
USAGE_LOG = os.path.join(DATA, "usage.jsonl")


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    return s


def save_settings(new):
    s = load_settings()
    s.update({k: v for k, v in new.items() if k in DEFAULT_SETTINGS})
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
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
               redstone=False, warnings=None):
    bid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = _dir(bid)
    os.makedirs(d)
    data = exporters.to_dict(blocks)
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
        "redstone": redstone, "warnings": warnings or [],
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


def delete_build(bid):
    import shutil
    shutil.rmtree(_dir(bid))


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
