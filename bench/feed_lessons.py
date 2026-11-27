"""Feed a finished bench run into the mistake stats (so the top mistakes come back as build lessons).
python bench/feed_lessons.py <label> [--stats <path to mistake_stats.json>]   (label = folder in bench/out)
Builds already recorded are skipped, so running it twice is safe."""
import glob, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from blockforge import mistake_stats as MS

args = sys.argv[1:]
if "--stats" in args:
    MS.PATH = args[args.index("--stats") + 1]
label = args[0] if args and not args[0].startswith("--") else ""
folder = os.path.join(ROOT, "bench", "out", label)
files = sorted(glob.glob(os.path.join(folder, "results*.jsonl"))) if label else []
if not files:
    sys.exit(f"No results*.jsonl in {folder}")
new = seen = 0
for fp in files:
    for line in open(fp, encoding="utf-8"):
        if line.strip():
            seen += 1
            new += 1 if MS.record_bench_row(json.loads(line)) or False else 0
print("FEED_OK", label, "builds", seen, "recorded", new, "->", MS.PATH)
for t, c, share, _ in MS.top(5):
    print(f"  {t}: {c} ({round(share * 100)}%)")
