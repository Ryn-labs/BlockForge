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


def run(code, timeout=90, placement_opts=None):
    """Returns (blocks_dict {(x,y,z): state}, meta). Raises ScriptError with a readable message."""
    check(code)
    proc = subprocess.run(
        runner_cmd(),
        input=code.encode("utf-8"), capture_output=True, timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
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
        rep = placement.process(blocks, **(placement_opts or {}))
        meta["fixes"] = rep["fixed"]
        meta["warnings"] = meta["redstone_warnings"] + rep["problems"]
    except Exception as e:                               # noqa: BLE001 - never lose a build over the checker
        meta["fixes"] = []
        meta.setdefault("warnings", []).append(f"placement check failed: {e}")
    if not blocks:
        raise ScriptError("The script ran but placed no blocks.")
    return blocks, meta


def run_safe(code, timeout=90, placement_opts=None):
    try:
        return run(code, timeout, placement_opts)
    except subprocess.TimeoutExpired:
        raise ScriptError(f"The script took longer than {timeout}s (too many blocks or an endless loop).")
