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
    try:
        exec(compile(code, "build.py", "exec"), g)
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        line = next((f.lineno for f in reversed(tb) if f.filename == "build.py"), None)
        err = f"{type(e).__name__}: {e}" + (f" (line {line})" if line else "")
    blocks = buildkit._blocks
    if not err and blocks:
        xs, ys, zs = zip(*blocks)
        span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) + 1
        if span > buildkit.MAX_SPAN:
            err = f"Build is {span} blocks across; the limit is {buildkit.MAX_SPAN}."
    pal, flat = {}, []
    if not err:
        for (x, y, z), st in blocks.items():
            flat += [x, y, z, pal.setdefault(st, len(pal))]
    real_out.write(json.dumps({"error": err, "palette": list(pal), "blocks": flat, "meta": buildkit._meta}))


if __name__ == "__main__":
    main()
