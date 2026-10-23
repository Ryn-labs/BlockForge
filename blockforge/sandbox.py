"""Run a build script in a separate, locked-down Python process and return its blocks."""
import ast
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED_IMPORTS = {"math", "random", "itertools", "functools", "collections", "colorsys"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "input", "globals", "locals", "vars", "getattr", "setattr",
                "delattr", "breakpoint", "__import__", "memoryview", "help", "exit", "quit", "type", "object",
                "super", "classmethod", "staticmethod", "property"}


def runner_cmd():
    if getattr(sys, "frozen", False):          # installed app: the console helper exe runs scripts
        return [os.path.join(os.path.dirname(sys.executable), "blockforge-cli.exe"), "--run-script"]
    return [sys.executable, "-I", os.path.join(HERE, "_runner.py")]


class ScriptError(Exception):
    pass


def check(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ScriptError(f"SyntaxError on line {e.lineno}: {e.msg}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise ScriptError(f"line {node.lineno}: import of '{a.name}' is not allowed "
                                      f"(only {', '.join(sorted(ALLOWED_IMPORTS))})")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                raise ScriptError(f"line {node.lineno}: import from '{node.module}' is not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ScriptError(f"line {node.lineno}: private attribute '{node.attr}' is not allowed")
        elif isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in BANNED_NAMES):
            raise ScriptError(f"line {node.lineno}: '{node.id}' is not allowed in build scripts")


def run(code, timeout=90, placement_opts=None, base=None):
    """Returns (blocks_dict {(x,y,z): state}, meta). Raises ScriptError with a readable message."""
    check(code)
    env, base_file = None, None
    if base:
        import tempfile
        fd, base_file = tempfile.mkstemp(suffix=".json", prefix="bf_base_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"blocks": [[x, y, z, s] for (x, y, z), s in base[0].items()],
                       "tiles": [[x, y, z, t] for (x, y, z), t in (base[1] or {}).items()]}, f)
        env = dict(os.environ, BLOCKFORGE_BASE=base_file)
    try:
        proc = subprocess.run(
            runner_cmd(),
            input=code.encode("utf-8"), capture_output=True, timeout=timeout, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        if base_file:
            try:
                os.remove(base_file)
            except OSError:
                pass
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0 or not out.startswith("{"):
        err = proc.stderr.decode("utf-8", "replace").strip() or out.strip() or "script crashed"
        raise ScriptError(err[-3000:])
    res = json.loads(out)
    if res.get("error"):
        raise ScriptError(res["error"])
    pal = res["palette"]
    f = res["blocks"]
    blocks = {(f[i], f[i + 1], f[i + 2]): pal[f[i + 3]] for i in range(0, len(f), 4)}
    if not blocks:
        raise ScriptError("The script ran but placed no blocks.")
    meta = res.get("meta") or {}
    meta["redstone_warnings"] = list(meta.get("warnings") or [])
    try:
        from . import placement
        rep = placement.process(blocks, **(placement_opts or {}), only=scope(meta) if base else None)
        restore_modules(blocks, meta)
        meta["fixes"] = rep["fixed"]
        meta["warnings"] = meta["redstone_warnings"] + rep["problems"]
        if base:
            protect_base(blocks, meta, base[0])
            meta["warnings"] = only_near_changes(meta["warnings"], meta)
            meta["redstone_warnings"] = only_near_changes(meta["redstone_warnings"], meta)
    except Exception as e:                               # noqa: BLE001 - never lose a build over the checker
        meta["fixes"] = []
        meta.setdefault("warnings", []).append(f"placement check failed: {e}")
    if not blocks:
        raise ScriptError("The script ran but placed no blocks.")
    return blocks, meta


def restore_modules(blocks, meta):
    """Proven machines must stay exactly as designed, whatever the auto-fixers did."""
    for x, y, z, s in meta.get("module_cells") or []:
        cur = blocks.get((x, y, z))
        if s.startswith("minecraft:redstone_wire") and cur and cur.startswith("minecraft:redstone_wire"):
            continue
        blocks[(x, y, z)] = s


def _near(meta):
    if "_near" not in meta:
        near = set()
        for x, y, z in meta.get("changed") or []:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        near.add((x + dx, y + dy, z + dz))
        meta["_near"] = near
    return meta["_near"]


def scope(meta):
    """Positions the placement checker may look at when editing an existing build (None = everything)."""
    return _near(meta) if "changed" in meta else None


def protect_base(blocks, meta, base_blocks):
    """Editing an existing build: only the AI's changes (and fixes right next to them) may differ from the original."""
    near = _near(meta)
    for p, s in base_blocks.items():
        if p not in near and blocks.get(p) != s:
            blocks[p] = s
    for p in [p for p in blocks if p not in base_blocks and p not in near]:
        del blocks[p]


def only_near_changes(messages, meta):
    """Keep only checker messages about blocks the AI changed (an imported build's own quirks aren't the AI's problem)."""
    import re
    near = _near(meta)
    keep = []
    for m in messages or []:
        pts = [tuple(int(v) for v in t) for t in re.findall(r"\((-?\d+), (-?\d+), (-?\d+)\)", m)]
        if pts and any(p in near for p in pts):
            keep.append(m)
    return keep


def tiles_of(meta):
    return {(x, y, z): t for x, y, z, t in meta.get("tiles") or []}


def run_safe(code, timeout=90, placement_opts=None, base=None):
    try:
        return run(code, timeout, placement_opts, base)
    except subprocess.TimeoutExpired:
        raise ScriptError(f"The script took longer than {timeout}s (too many blocks or an endless loop).")
