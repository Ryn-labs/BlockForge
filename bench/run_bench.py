"""BlockForge benchmark: the 10 fixed prompts through the real generate path, headless, on TEMP data (never the real gallery).
Each build is scored by bench/score.py and rendered by bench/render.py. Results: bench/out/<version>/results.jsonl + table.md + renders.
python bench/run_bench.py [--only 1,2] [--model claude-opus-5-5] [--research]   -> BENCH_OK <version> total <mistakes>
Runs one build at a time (memory). Engine: Claude Code (claude -p), like the app's default."""
import os, sys, json, time, tempfile, traceback, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from blockforge.version import VERSION
VERSION = os.environ.get("BENCH_LABEL") or VERSION
OUT = os.path.join(ROOT, "bench", "out", VERSION); os.makedirs(OUT, exist_ok=True)
REAL_DATA = os.environ.get("BLOCKFORGE_DATA") or os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "BlockForge")
os.environ["BLOCKFORGE_DATA"] = os.environ.get("BLOCKFORGE_DATA") or os.path.join(tempfile.gettempdir(), f"bf-bench-{VERSION}")
os.environ.setdefault("BLOCKFORGE_PORT", "8799")
from blockforge import engine, store, prompts as P
sys.path.insert(0, os.path.join(ROOT, "bench"))
import score as SC, render as RD
from blockforge import mistake_stats as MS
MS.PATH = os.environ.get("BENCH_STATS") or os.path.join(OUT, "mistake_stats.json")   # bench stats stay with the bench; the real app data is never written (set BENCH_STATS to feed an app on purpose)

args = sys.argv[1:]
ONLY = {int(v) for v in args[args.index("--only") + 1].split(",")} if "--only" in args else None
MODEL = args[args.index("--model") + 1] if "--model" in args else None
RESEARCH = "--research" in args
ENGINE = args[args.index("--engine") + 1] if "--engine" in args else "claude_code"
PROMPTS = json.load(open(os.path.join(ROOT, "bench", "prompts.json")))
TAG = os.environ.get("BENCH_TAG", "")
res_path = os.path.join(OUT, f"results{'-' + TAG if TAG else ''}.jsonl")   # parallel workers write their own file
done = {}
if os.path.exists(res_path):
    for l in open(res_path, encoding="utf-8"):
        r = json.loads(l); done[r["id"]] = r
KEYS = ("floating", "removed", "overwritten", "buried_path", "jump_steps", "corner_turns", "blocked_doors", "wrong_facing", "size_off",
        "script_errors", "fix_rounds")
for p in PROMPTS:
    if ONLY and p["id"] not in ONLY: continue
    logs = []; t0 = time.time(); r = {"id": p["id"], "key": p["key"], "version": VERSION}
    parent = done.get(p.get("edit_of"), {}).get("build") if p.get("edit_of") else None
    try:
        meta = engine.generate(p["prompt"], size=p["size"], palette="auto", model=MODEL, engine=ENGINE, parent_id=parent,
                               research=RESEARCH, redstone=False, use_mods=False, log=lambda m: logs.append(str(m)))
        r["build"] = meta["id"]; d = os.path.join(str(store.BUILDS), meta["id"])
        lo, hi = P.PRESET_RANGES.get(p["size"], (None, None)) if not p.get("edit_of") else (None, None)
        r.update(SC.score(d, lo, hi))
        cp = os.path.join(d, "code.py")
        r["overwritten"] = SC.overwritten(open(cp, encoding="utf-8").read()) if os.path.exists(cp) else -1
        u = meta.get("usage") or {}
        r["cost"] = round(float(u.get("cost") or u.get("cost_usd") or 0), 3)
        RD.sheet(d, os.path.join(OUT, f"{p['id']:02d}-{p['key']}.png"))
        r["size"] = meta.get("size")
    except Exception as e:                                                  # a failed build is a result, never hidden
        r["error"] = f"{type(e).__name__}: {e}"[:300]; traceback.print_exc()
    r["script_errors"] = sum(1 for l in logs if l.startswith("Script error"))
    r["fix_rounds"] = sum(1 for l in logs if l.startswith("Asking "))
    r["time_s"] = round(time.time() - t0)
    r["mistakes"] = sum(max(0, r.get(k, 0)) for k in KEYS if k not in ("fix_rounds",)) + (1 if r.get("error") else 0)
    try: MS.record_bench_row(r)                                             # top mistakes come back as lessons
    except Exception: traceback.print_exc()
    open(os.path.join(OUT, f"{p['id']:02d}-{p['key']}.log"), "w", encoding="utf-8").write("\n".join(logs))
    done[p["id"]] = r
    with open(res_path, "w", encoding="utf-8") as f:
        for k in sorted(done): f.write(json.dumps(done[k]) + "\n")
    print("BENCH_BUILD", p["id"], p["key"], "mistakes", r["mistakes"], {k: r.get(k) for k in KEYS if r.get(k)}, "time", r["time_s"], r.get("error", ""), flush=True)
cols = ["id", "key"] + list(KEYS) + ["mistakes", "time_s", "cost"]
rows = [done[k] for k in sorted(done)]
tab = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
for r in rows: tab.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
tot = {c: sum(max(0, r.get(c, 0) or 0) for r in rows) for c in cols[2:]}
tab.append("| total | | " + " | ".join(str(round(tot[c], 2)) for c in cols[2:]) + " |")
open(os.path.join(OUT, "table.md"), "w", encoding="utf-8").write(f"# BlockForge {VERSION} benchmark\n\n" + "\n".join(tab) + "\n")
print("BENCH_OK", VERSION, "builds", len(rows), "total", tot["mistakes"], "time", tot["time_s"], "cost", tot["cost"])
