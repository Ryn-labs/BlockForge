"""Merge bench results (results*.jsonl of one version) into table.md: every check per build, totals with and without overwrites,
and a before/after column block when a second version is given.
python bench/table.py <version> [<baseline version>]   -> TABLE_OK <version> mistakes <n> (excl. overwrites <m>)"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ("floating", "removed", "overwritten", "buried_path", "jump_steps", "corner_turns", "blocked_doors", "wrong_facing", "size_off",
        "terrain_floating", "terrain_buried", "script_errors", "fix_rounds")
def rows(v):
    d = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "bench", "out", v, "results*.jsonl"))):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l); d[r["id"]] = r
    for r in d.values():
        r["mistakes"] = sum(max(0, r.get(k, 0) or 0) for k in KEYS if k != "fix_rounds") + (1 if r.get("error") else 0)
        r["mistakes_ex_ow"] = r["mistakes"] - max(0, r.get("overwritten", 0) or 0)
    return [d[k] for k in sorted(d)]
v = sys.argv[1]; R = rows(v); base = rows(sys.argv[2]) if len(sys.argv) > 2 else None
cols = ["id", "key"] + list(KEYS) + ["mistakes", "mistakes_ex_ow", "quality", "time_s", "cost"]
out = [f"# BlockForge {v} benchmark", "", "Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks "
       "(scripts that fill then carve overwrite on purpose, so that column is mostly style). `quality` is the building quality "
       "score 0-100 (higher is better, empty for non-buildings; the total row is the average).", "",
       "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
for r in R: out.append("| " + " | ".join(("" if r.get(c) is None and c == "quality" else str(r.get(c, r.get("error", "")[:20] if c == "key" and r.get("error") else ""))) if c != "key" else r["key"] + (" (ERROR)" if r.get("error") else "") for c in cols) + " |")


def _avg_quality(rows):
    qs = [r["quality"] for r in rows if r.get("quality") is not None]
    return round(sum(qs) / len(qs)) if qs else 0


tot = {c: round(sum(max(0, r.get(c, 0) or 0) for r in R), 2) for c in cols[2:]}
tot["quality"] = _avg_quality(R)
out.append("| total | | " + " | ".join(str(tot[c]) for c in cols[2:]) + " |")
if base:
    bt = {c: round(sum(max(0, r.get(c, 0) or 0) for r in base), 2) for c in cols[2:]}
    bt["quality"] = _avg_quality(base)
    out += ["", f"## {sys.argv[2]} -> {v}", "", "| check | before | after | change |", "|---|---|---|---|"]
    for c in cols[2:]:
        ch = "" if not bt[c] else f"{round(100 * (tot[c] - bt[c]) / bt[c])}%"
        out.append(f"| {c} | {bt[c]} | {tot[c]} | {ch} |")
open(os.path.join(ROOT, "bench", "out", v, "table.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("TABLE_OK", v, "mistakes", tot["mistakes"], "excl. overwrites", tot["mistakes_ex_ow"], "time", tot["time_s"], "cost", tot["cost"])
