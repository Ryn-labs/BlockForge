"""The local learning loop. Everything stays on this PC.

What it records:
  quality.jsonl      one line per build: which automatic fixes / problems the checker hit, and later the thumbs rating.
  corrections.jsonl  when you hand-edit an AI build and run it, the "AI version -> your fixed version" pair.
What it does with that:
  examples_for()     your best builds (thumbs up, or ones you fixed by hand) are shown to the AI as examples when a new
                     request looks similar, so results get closer to your taste without any retraining.
  stats()            what the Settings -> Learning tab shows.
"""
import json
import os
import re
import time

from . import store

QUALITY_LOG = os.path.join(store.DATA, "quality.jsonl")
CORRECTIONS_LOG = os.path.join(store.DATA, "corrections.jsonl")
AI_SOURCES = ("claude_code", "api", "claude_chat") + ("openai", "openrouter", "groq", "gemini", "ollama", "custom")
RATING_TAGS = ["wrong style", "broken structure", "too small", "ugly roof", "floating or missing blocks", "not what I asked"]

_STOP = set("a an the of in on with and or for to from at by is are it that this make build me my some very big small large "
            "tiny huge please want like have has into out up down all each over under around inside outside".split())


def _tokens(text):
    return {t for t in re.findall(r"[a-z]+", (text or "").lower()) if len(t) > 2 and t not in _STOP}


def _append(path, obj):
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, separators=(",", ":")) + "\n")
    except OSError:
        pass                                                  # logging must never break a build


def _read(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def log_enabled():
    return store.load_settings().get("learn_log", True)


# ---------------------------------------------------------------- recording
def log_generation(meta, fixes=None, problems=None):
    if not log_enabled():
        return
    _append(QUALITY_LOG, {"t": round(time.time()), "event": "build", "id": meta["id"], "source": meta.get("source"),
                          "model": meta.get("model"), "prompt": (meta.get("prompt") or "")[:300],
                          "redstone": bool(meta.get("redstone")), "modpack": meta.get("modpack"),
                          "fixes": fixes or [], "problems": problems or []})


def rate(bid, rating, tags=None, note=""):
    """rating: 'up', 'down' or None (clear)."""
    if rating not in ("up", "down", None):
        raise ValueError("rating must be up, down or null")
    tags = [t for t in (tags or []) if t in RATING_TAGS][:6] if rating == "down" else []
    meta = store.update_meta(bid, rating=rating, rating_tags=tags, rating_note=(note or "")[:300],
                             rated=round(time.time()) if rating else None)
    if log_enabled():
        _append(QUALITY_LOG, {"t": round(time.time()), "event": "rating", "id": bid, "rating": rating, "tags": tags,
                              "prompt": (meta.get("prompt") or "")[:300]})
    return meta


def log_correction(parent_id, child_id):
    """You edited an AI-made build's script and ran it: keep the before/after pair."""
    try:
        parent = store.get_meta(parent_id)
        before, after = store.get_code(parent_id), store.get_code(child_id)
    except (KeyError, OSError):
        return
    if not before or not after or before == after:
        return
    if parent.get("source") not in AI_SOURCES and not parent.get("corrects"):
        return
    store.update_meta(child_id, corrects=parent_id)
    if log_enabled():
        _append(CORRECTIONS_LOG, {"t": round(time.time()), "parent": parent_id, "child": child_id,
                                  "prompt": (parent.get("prompt") or "")[:300], "before": before[:30000], "after": after[:30000]})


# ---------------------------------------------------------------- using it
def examples_for(prompt, limit=2, budget=7000):
    """The player's best builds that look like this request: [(title, prompt, code)]."""
    want = _tokens(prompt)
    if len(want) < 1:
        return []
    scored = []
    for m in store.list_builds():
        liked = m.get("rating") == "up" or (m.get("corrects") and m.get("rating") != "down")
        if not liked or m.get("rating") == "down":
            continue
        have = _tokens((m.get("prompt") or "") + " " + (m.get("title") or ""))
        shared = want & have
        if not shared:
            continue
        score = len(shared) / (len(want | have) or 1) + (0.05 if m.get("rating") == "up" else 0)
        if score >= 0.12:
            scored.append((score, m))
    scored.sort(key=lambda x: -x[0])
    out, used = [], 0
    for _, m in scored:
        code = store.get_code(m["id"])
        if not code or used + len(code) > budget:
            continue
        out.append((m.get("title") or "Build", m.get("prompt") or "", code))
        used += len(code)
        if len(out) >= limit:
            break
    return out


def common_mistakes(limit=4, window=60, min_count=3):
    """What the checker had to fix again and again in recent AI builds: [(text, times)]."""
    builds = [r for r in _read(QUALITY_LOG) if r.get("event") == "build" and r.get("source") in AI_SOURCES][-window:]
    seen = {}
    for r in builds:
        for f in set(re.sub(r"\s*\(×\d+\)", "", x) for x in r.get("fixes", []) + r.get("problems", [])):
            if f.startswith(("...and more", "Made leaves persistent")):
                continue
            key = re.sub(r" at \(.*?\)$", "", f)[:160]
            seen[key] = seen.get(key, 0) + 1
    return [(k, n) for k, n in sorted(seen.items(), key=lambda kv: -kv[1]) if n >= min_count][:limit]


def prompt_section(prompt):
    if not store.load_settings().get("learn_examples", True):
        return None
    parts = []
    mistakes = common_mistakes()
    if mistakes:
        parts.append("## Mistakes to avoid (BlockForge's checker keeps having to fix these in your builds)\n" +
                     "\n".join(f"- {t}" for t, _ in mistakes) + "\nGet these right in the script so no fix is needed.")
    ex = examples_for(prompt)
    if ex:
        parts.append("## Builds this player liked (use them to match their taste)\n"
                     "These earlier scripts got a thumbs up or were fixed by hand by the player. Learn their style, proportions "
                     "and level of detail. Do NOT copy them: design something new for the request below.")
        for title, p, code in ex:
            parts.append(f"### {title} (request: {p[:160]})\n```python\n{code}\n```")
    return "\n\n".join(parts) or None


# ---------------------------------------------------------------- reporting
def stats():
    builds = store.list_builds()
    q = _read(QUALITY_LOG)
    fixes = {}
    for r in q:
        if r.get("event") != "build":
            continue
        for f in r.get("fixes", []) + r.get("problems", []):
            key = re.sub(r"\s*\(×\d+\)|:.*$", "", f)[:90]
            fixes[key] = fixes.get(key, 0) + 1
    tags = {}
    for m in builds:
        for t in m.get("rating_tags") or []:
            tags[t] = tags.get(t, 0) + 1
    return {"builds": len(builds), "up": sum(1 for m in builds if m.get("rating") == "up"),
            "down": sum(1 for m in builds if m.get("rating") == "down"),
            "corrections": len(_read(CORRECTIONS_LOG)), "checked": sum(1 for r in q if r.get("event") == "build"),
            "top_fixes": sorted(fixes.items(), key=lambda kv: -kv[1])[:6],
            "down_tags": sorted(tags.items(), key=lambda kv: -kv[1])}


def clear():
    for p in (QUALITY_LOG, CORRECTIONS_LOG):
        try:
            os.remove(p)
        except OSError:
            pass
    for m in store.list_builds():
        if m.get("rating") or m.get("corrects"):
            try:
                store.update_meta(m["id"], rating=None, rating_tags=[], rating_note="", rated=None, corrects=None)
            except (KeyError, OSError):
                pass
