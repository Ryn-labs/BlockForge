"""Rolling count of the building AI's mistakes, fed back into the build lessons.

DATA/mistake_stats.json keeps the last WINDOW builds (bench runs and the app's own builds): per build a count per
mistake type and up to 3 example sentences. top() ranks the types over that window; lesson_lines() turns the worst
ones into short imperative lines for the AI (lessons.for_ai puts them in front of the static lessons).
"""
import json
import os
import time

from . import store

WINDOW = 50
PER_BUILD_CAP = 10          # one build with hundreds of one kind must not drown the other types
EXAMPLES = 3
PATH = os.path.join(store.DATA, "mistake_stats.json")

FIX_LINES = {
    "buried_path": "Keep 2 free blocks over every step and path; never run a path into a hill or under a block",
    "jump_steps": "Every 1-block rise on a path is a bottom stair facing uphill",
    "size_off": "Build to the asked size: check the size before you save",
    "floating": "Every part must touch the ground or another part; add a post, wall or beam under anything that hangs",
    "removed": "Hang lanterns from something or stand them on something; torches need a wall",
    "corner_turns": "Turn stairs on a flat landing, never in the middle of a slope",
    "wrong_facing": "Stairs, doors and trapdoors face the way people walk; check each facing after you place it",
    "blocked_doors": "Keep the 2 blocks in front of every door free, with a floor to stand on",
    "overwritten": "Plan parts so you don't fill and then carve the same blocks",
}
LABELS = {"buried_path": "buried paths", "jump_steps": "jump steps", "size_off": "wrong size", "floating": "floating parts",
          "removed": "removed blocks", "corner_turns": "corner turns", "wrong_facing": "wrong facings",
          "blocked_doors": "blocked doors", "overwritten": "overwritten blocks"}
TYPES = tuple(FIX_LINES)
# checks.py names (and the bench score names) -> mistake types
CHECK_MAP = {"floating": "floating", "buried_path": "buried_path", "headroom": "buried_path", "jump_step": "jump_steps",
             "jump_steps": "jump_steps", "corner_turn": "corner_turns", "corner_turns": "corner_turns",
             "wrong_facing": "wrong_facing", "door_blocked": "blocked_doors", "blocked_doors": "blocked_doors",
             "size_off": "size_off", "removed": "removed", "overwritten": "overwritten"}


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("builds"), list) else {"builds": []}
    except (OSError, ValueError):
        return {"builds": []}


def _counts_of(src):
    """Mistake counts from a build meta (meta['checks']['by_check']), a {'by_check': ..} dict or a plain counts dict."""
    if not isinstance(src, dict):
        return {}
    raw = src.get("checks", {}).get("by_check") if isinstance(src.get("checks"), dict) else None
    raw = raw if raw is not None else src.get("by_check", src)
    out = {}
    for k, v in (raw or {}).items():
        t = CHECK_MAP.get(k)
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if t and n > 0:
            out[t] = min(PER_BUILD_CAP, out.get(t, 0) + n)
    return out


def record(src, source="app", key=None, examples=None, build_id=None):
    """Add one build. examples = {type or check name: [sentence, ...]}. Returns the counts recorded (empty = none)."""
    counts = _counts_of(src)
    ex = {}
    for k, lst in (examples or {}).items():
        t = CHECK_MAP.get(k)
        if t:
            ex.setdefault(t, []).extend(str(s)[:200] for s in lst)
    d = _load()
    if build_id and any(b.get("id") == build_id for b in d["builds"]):
        return {}
    d["builds"].append({"t": int(time.time()), "source": source, "key": key, "id": build_id, "counts": counts,
                        "ex": {t: ex[t][:EXAMPLES] for t in ex if t in counts}})
    d["builds"] = d["builds"][-WINDOW:]
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, PATH)
    except OSError:
        pass
    return counts


def record_findings(found, source="app", key=None, build_id=None, size_off=0):
    """Record a checks.run() result (findings carry the example sentences)."""
    counts, ex = {}, {}
    for f in found:
        counts[f["check"]] = max(counts.get(f["check"], 0), f.get("count", 1))
        ex.setdefault(f["check"], []).append(f["text"])
    if size_off:
        counts["size_off"] = size_off
    return record(counts, source, key, ex, build_id)


def top(n=5):
    """[(type, count, share, examples)] worst first; share is of all mistakes in the window (0..1)."""
    tot, ex = {}, {}
    for b in _load()["builds"]:
        for t, c in (b.get("counts") or {}).items():
            tot[t] = tot.get(t, 0) + c
        for t, lst in (b.get("ex") or {}).items():
            ex.setdefault(t, []).extend(lst)
    allc = sum(tot.values())
    rows = sorted(tot.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(t, c, c / allc, ex.get(t, [])[-EXAMPLES:]) for t, c in rows[:max(0, int(n))] if c > 0]


def lesson_lines(n=5):
    """Short imperative lines for the worst types, with their share."""
    return [f"{FIX_LINES[t]} ({round(share * 100)}% of recent mistakes: {LABELS[t]})" for t, c, share, _ in top(n)]


def record_bench_row(row):
    """Record one scored bench build (a results.jsonl row). Builds that failed outright are skipped. Same build twice = once."""
    if row.get("error") or not isinstance(row, dict):
        return {}
    bid = row.get("build") or f"{row.get('version')}:{row.get('id')}"
    counts = {k: v for k, v in row.items() if k in CHECK_MAP and isinstance(v, int) and v > 0}
    ex = {k: [f"{k.replace('_', ' ')}: {v} in the '{row.get('key')}' bench build"] for k, v in counts.items()}
    return record(counts, "bench", row.get("key"), ex, bid)
