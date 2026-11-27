"""Merge bench results (results*.jsonl of one version) into table.md: every check per build, totals with and without overwrites,
and a before/after column block when a second version is given.
python bench/table.py <version> [<baseline version>]   -> TABLE_OK <version> mistakes <n> (excl. overwrites <m>)"""
import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ("floating", "removed", "overwritten", "buried_path", "jump_steps", "corner_turns", "blocked_doors", "wrong_facing", "size_off",
        "script_errors", "fix_rounds")
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
cols = ["id", "key"] + list(KEYS) + ["mistakes", "mistakes_ex_ow", "time_s", "cost"]
out = [f"# BlockForge {v} benchmark", "", "Lower is better. `mistakes` counts every check; `mistakes_ex_ow` leaves out overwritten blocks "
       "(scripts that fill then carve overwrite on purpose, so that column is mostly style).", "",
       "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
for r in R: out.append("| " + " | ".join(str(r.get(c, r.get("error", "")[:20] if c == "key" and r.get("error") else "")) if c != "key" else r["key"] + (" (ERROR)" if r.get("error") else "") for c in cols) + " |")
tot = {c: round(sum(max(0, r.get(c, 0) or 0) for r in R), 2) for c in cols[2:]}
out.append("| total | | " + " | ".join(str(tot[c]) for c in cols[2:]) + " |")
if base:
    bt = {c: round(sum(max(0, r.get(c, 0) or 0) for r in base), 2) for c in cols[2:]}
    out += ["", f"## {sys.argv[2]} -> {v}", "", "| check | before | after | change |", "|---|---|---|---|"]
    for c in cols[2:]:
        ch = "" if not bt[c] else f"{round(100 * (tot[c] - bt[c]) / bt[c])}%"
        out.append(f"| {c} | {bt[c]} | {tot[c]} | {ch} |")
open(os.path.join(ROOT, "bench", "out", v, "table.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("TABLE_OK", v, "mistakes", tot["mistakes"], "excl. overwrites", tot["mistakes_ex_ow"], "time", tot["time_s"], "cost", tot["cost"])
