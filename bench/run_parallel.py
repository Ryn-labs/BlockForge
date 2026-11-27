"""Run the benchmark in parallel: N workers at once, each its own temp BLOCKFORGE_DATA + port (8801..), then one merged table.
Prompt 10 edits prompt 1, so 1 and 10 run in the same worker.
python bench/run_parallel.py [--workers 5] [--model m]   -> BENCH_PAR_OK <version> total ...   (then bench/table.py)"""
import os, sys, json, subprocess, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from blockforge.version import VERSION
VERSION = os.environ.get("BENCH_LABEL") or VERSION
args = sys.argv[1:]
N = int(args[args.index("--workers") + 1]) if "--workers" in args else 5
extra = (["--model", args[args.index("--model") + 1]] if "--model" in args else []) + (["--engine", args[args.index("--engine") + 1]] if "--engine" in args else [])
groups = [[1, 10], [2], [3], [4], [5], [6], [7], [8], [9]]
procs = []; running = []
def start(k, g):
    env = dict(os.environ, BLOCKFORGE_DATA=os.path.join(tempfile.gettempdir(), f"bf-bench-{VERSION}-w{k}"), BENCH_LABEL=VERSION, BLOCKFORGE_PORT=str(8801 + k),
               BENCH_TAG=f"w{k}")
    log = open(os.path.join(ROOT, "bench", "out", f"par-{VERSION}-w{k}.log"), "w")
    return subprocess.Popen([sys.executable, "-I", os.path.join(ROOT, "bench", "run_bench.py"), "--only", ",".join(map(str, g))] + extra,
                            env=env, stdout=log, stderr=subprocess.STDOUT)
os.makedirs(os.path.join(ROOT, "bench", "out"), exist_ok=True)
queue = list(enumerate(groups))
while queue or running:
    while queue and len(running) < N:
        k, g = queue.pop(0); running.append(start(k, g))
    running[0].wait(); running = [p for p in running if p.poll() is None]
subprocess.run([sys.executable, "-I", os.path.join(ROOT, "bench", "table.py"), VERSION])
