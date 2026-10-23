"""Child process: read a build script on stdin, run it with the toolkit, print JSON blocks."""
import builtins
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blockforge import buildkit  # noqa: E402

SAFE_BUILTINS = {k: getattr(builtins, k) for k in (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "frozenset", "int",
    "isinstance", "len", "list", "map", "max", "min", "pow", "print", "range", "reversed", "round", "set",
    "sorted", "str", "sum", "tuple", "zip", "chr", "ord", "hash", "iter", "next", "slice", "repr", "format",
    "Exception", "ValueError", "IndexError", "KeyError", "ZeroDivisionError", "StopIteration", "True", "False",
    "None", "callable", "bin", "hex",
) if hasattr(builtins, k)}
_real_import = builtins.__import__


def _import(name, *a, **k):
    if name.split(".")[0] in ("math", "random", "itertools", "functools", "collections", "colorsys"):
        return _real_import(name, *a, **k)
    raise ImportError(f"import of {name} is not allowed")


SAFE_BUILTINS["__import__"] = _import


def main():
    code = sys.stdin.buffer.read().decode("utf-8")
    real_out = sys.stdout
    sys.stdout = sys.stderr            # script prints go to stderr, keep stdout for the result
    g = {"__builtins__": SAFE_BUILTINS, "__name__": "build"}
    for n in buildkit.EXPORTS:
        g[n] = getattr(buildkit, n)
    err = None
    base = {}
    base_path = os.environ.get("BLOCKFORGE_BASE")
    if base_path:                                    # editing an existing build: its blocks are already placed
        with open(base_path, encoding="utf-8") as f:
            b = json.load(f)
        for x, y, z, s in b["blocks"]:
            buildkit._blocks[(x, y, z)] = s
        for x, y, z, t in b.get("tiles") or []:
            buildkit._tiles[(x, y, z)] = t
        base = dict(buildkit._blocks)
    try:
        exec(compile(code, "build.py", "exec"), g)
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        line = next((f.lineno for f in reversed(tb) if f.filename == "build.py"), None)
        err = f"{type(e).__name__}: {e}" + (f" (line {line})" if line else "")
    blocks = buildkit._blocks
    changed = set()
    if base and not err:
        changed = {p for p in set(base) | set(blocks) if base.get(p) != blocks.get(p)}
        if not changed:
            err = ("Your script didn't change anything. The build's blocks are already placed when the script starts, "
                   "so write the code that makes the requested change.")
    if not err and buildkit._modules:
        broken = buildkit._modules_lib.check_intact(blocks)
        if broken:
            err = ("Your script built over a proven redstone machine, so it would not work in game: " + "; ".join(broken[:5]) +
                   ". Never place, replace or wire blocks inside a machine made by item_sorter() etc. Move your own blocks "
                   "outside its footprint.")
    if not err and blocks:
        try:
            buildkit._meta["warnings"] = buildkit._redstone.finalize(blocks)
            if buildkit._modules:                    # proven machines are checked in game, not by the simple checker
                cells = {p for m in buildkit._modules for p in m["cells"]}
                buildkit._meta["warnings"] = buildkit._redstone.check({p: s for p, s in blocks.items() if p not in cells})
        except Exception as e:                       # noqa: BLE001 - never lose a build over the checker
            buildkit._meta["warnings"] = [f"redstone check failed: {e}"]
        buildkit._modules_lib.restore(blocks, buildkit._modules)
        for p, s in base.items():                    # auto-wiring must not touch the parts of the build left alone
            if p not in changed:
                blocks[p] = s
    if not err and blocks:
        xs, ys, zs = zip(*blocks)
        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) + 1
        if span > buildkit.MAX_SPAN:
            err = f"Build is {span} blocks across; the limit is {buildkit.MAX_SPAN}."
    pal, flat = {}, []
    if not err:
        for (x, y, z), st in blocks.items():
            flat += [x, y, z, pal.setdefault(st, len(pal))]
    if not err:
        tiles = []
        for p, t in buildkit._tiles.items():
            st = blocks.get(p)
            if st and st.split("[", 1)[0] == t.get("id"):        # keep contents only while the container is still there
                tiles.append([p[0], p[1], p[2], t])
        buildkit._meta["tiles"] = tiles
        buildkit._meta["module_cells"] = [[p[0], p[1], p[2], s] for m in buildkit._modules for p, s in m["cells"].items()]
        buildkit._meta["entities"] = buildkit._entities
        buildkit._meta["tests"] = buildkit._tests + [t for m in buildkit._modules for t in m.get("tests", [])]
        buildkit._meta["modules"] = [m["name"] for m in buildkit._modules]
        if base:
            buildkit._meta["changed"] = [list(p) for p in changed]
    real_out.write(json.dumps({"error": err, "palette": list(pal), "blocks": flat, "meta": buildkit._meta}))


if __name__ == "__main__":
    main()
