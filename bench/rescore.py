"""Re-score saved bench builds with the current score.py (no AI calls): finds each build by id in the temp bench data folders,
recomputes the block checks (overwritten and run stats are kept), writes the results into a new label folder <label>-v2.
python bench/rescore.py <label> [<label> ...]   -> RESCORE_OK <label> builds n missing m"""
import os, sys, json, glob, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import score as SC
RANGES = {"tiny": (8, 12), "small": (16, 24), "medium": (32, 48), "large": (64, 96), "huge": (128, 200)}
P = {p["id"]: p for p in json.load(open(os.path.join(HERE, "prompts.json")))}
DIRS = glob.glob(os.path.join(tempfile.gettempdir(), "bf-bench*", "builds"))
for label in sys.argv[1:]:
    rows = [json.loads(l) for f in glob.glob(os.path.join(HERE, "out", label, "results*.jsonl")) for l in open(f, encoding="utf-8")]
    out = os.path.join(HERE, "out", label + "-v2"); os.makedirs(out, exist_ok=True); miss = 0; res = []
    for r in rows:
        d = next((os.path.join(x, r.get("build", "")) for x in DIRS if r.get("build") and os.path.isdir(os.path.join(x, r["build"]))), None)
        if not d:
            miss += 1; res.append(r); continue
        p = P[r["id"]]; lo, hi = RANGES.get(p["size"], (None, None)) if not p.get("edit_of") else (None, None)
        r.update(SC.score(d, lo, hi)); res.append(r)
    with open(os.path.join(out, "results.jsonl"), "w", encoding="utf-8") as f:
        for r in sorted(res, key=lambda r: r["id"]): f.write(json.dumps(r) + "\n")
    print("RESCORE_OK", label, "builds", len(rows), "missing", miss)
