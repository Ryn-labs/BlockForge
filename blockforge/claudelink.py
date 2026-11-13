"""Connect BlockForge to Claude.

- Claude Code: adds the BlockForge MCP server for every folder (user scope) and a /blockforge command.
- Claude Desktop: adds the BlockForge MCP server to claude_desktop_config.json.

Only the "blockforge" entries are touched. Before a config file is changed it is copied to
<file>.blockforge.bak, and a file that isn't valid JSON is never rewritten.
BLOCKFORGE_CLAUDE_HOME / BLOCKFORGE_CLAUDE_APPDATA point everything at a test folder.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

NAME = "blockforge"
MARK = "<!-- made by BlockForge -->"
TEST = bool(os.environ.get("BLOCKFORGE_CLAUDE_HOME"))
HOME = os.environ.get("BLOCKFORGE_CLAUDE_HOME") or os.path.expanduser("~")
APPDATA = os.environ.get("BLOCKFORGE_CLAUDE_APPDATA") or (os.path.join(HOME, "AppData", "Roaming") if TEST
                                                          else os.environ.get("APPDATA") or HOME)

COMMAND = MARK + """
Use the BlockForge tools (the `blockforge` MCP server) for this: $ARGUMENTS

- Nothing, or "open": call `app_open`, then mention the 5 newest builds (`list_builds` with limit 5).
- "close": call `app_close`. If it says a build is still being made, ask before closing with force.
- "status": call `app_status`.
- "show <name or id>": find the build with `list_builds` (query), then `app_open` with its build_id.
- "export <name> as <format>": find it, then `export_build`.
- Anything else is a build request: call `get_build_guide`, write the script, `create_build`,
  then `app_open` with the new build_id so it's on screen in BlockForge.

If the blockforge tools aren't available, say: open BlockForge, go to Settings, AI, press "Connect to Claude",
then restart Claude.
"""
COMMAND_HEAD = """---
description: Talk to BlockForge - open or close the app, show or export a build, or make a new Minecraft build
argument-hint: "[open | close | status | show <build> | what to build]"
allowed-tools: mcp__blockforge
---
"""


def mcp_command():
    """(command, args) that starts BlockForge's MCP server."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "blockforge-cli.exe"), ["--mcp"]
    py = sys.executable
    if os.path.basename(py).lower() == "pythonw.exe" and os.path.exists(os.path.join(os.path.dirname(py), "python.exe")):
        py = os.path.join(os.path.dirname(py), "python.exe")
    return py, [os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_server.py")]


def _entry():
    cmd, args = mcp_command()
    return {"type": "stdio", "command": cmd, "args": args, "env": {}}


# ------------------------------------------------------------------ files
def code_config():
    return os.path.join(HOME, ".claude.json")


def command_file():
    return os.path.join(HOME, ".claude", "commands", "blockforge.md")


def desktop_configs():
    """Claude Desktop's config: the normal install, and the Microsoft Store install's private copy."""
    found = [os.path.join(APPDATA, "Claude", "claude_desktop_config.json")]
    local = os.environ.get("LOCALAPPDATA") if not TEST else os.path.join(HOME, "AppData", "Local")
    if local:
        for d in glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude")):
            found.append(os.path.join(d, "claude_desktop_config.json"))
    return [p for p in found if os.path.isdir(os.path.dirname(p))]


def claude_code_installed():
    return bool(_claude_cli()) or os.path.isdir(os.path.join(HOME, ".claude"))


def _claude_cli():
    if TEST:
        return None                                   # tests never touch the real Claude Code
    exe = shutil.which("claude")
    if not exe:
        p = os.path.join(HOME, ".local", "bin", "claude.exe")
        exe = p if os.path.exists(p) else None
    return exe


def _read(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        return {}
    data = json.loads(text)                           # ValueError: leave the file alone
    if not isinstance(data, dict):
        raise ValueError(f"{path} isn't a settings file")
    return data


def _edit(path, change):
    """Read-modify-write one JSON file, keeping a backup and replacing it in one step."""
    data = _read(path)
    if change(data) is False:
        return
    if os.path.exists(path):
        shutil.copy2(path, path + ".blockforge.bak")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".blockforge.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _run_cli(*args):
    exe = _claude_cli()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, *args], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ------------------------------------------------------------------ status / connect / disconnect
def _entry_ok(e):
    return isinstance(e, dict) and bool(e.get("command")) and os.path.exists(e["command"])


def status():
    out = {"command": " ".join([mcp_command()[0], *mcp_command()[1]])}
    try:
        e = (_read(code_config()).get("mcpServers") or {}).get(NAME)
        out["code"] = {"installed": claude_code_installed(), "linked": bool(e), "ok": _entry_ok(e),
                       "slash": os.path.exists(command_file())}
    except (OSError, ValueError) as ex:
        out["code"] = {"installed": True, "linked": False, "error": str(ex)}
    desk = desktop_configs()
    out["desktop"] = {"installed": bool(desk), "linked": False, "ok": False}
    for p in desk:
        try:
            e = (_read(p).get("mcpServers") or {}).get(NAME)
        except (OSError, ValueError) as ex:
            out["desktop"]["error"] = str(ex)
            continue
        if e:
            out["desktop"].update(linked=True, ok=_entry_ok(e))
    return out


def connect(targets=("code", "desktop")):
    done, problems = [], []
    if "code" in targets:
        if not claude_code_installed():
            problems.append("Claude Code isn't installed on this PC.")
        else:
            try:
                cmd, args = mcp_command()
                # the official way first (it also handles Claude Code being open); edit the file directly if that fails
                _run_cli("mcp", "remove", NAME, "--scope", "user")
                if not _run_cli("mcp", "add", "--scope", "user", NAME, "--", cmd, *args):
                    _edit(code_config(), lambda d: d.setdefault("mcpServers", {}).__setitem__(NAME, _entry()))
                os.makedirs(os.path.dirname(command_file()), exist_ok=True)
                with open(command_file(), "w", encoding="utf-8") as f:
                    f.write(COMMAND_HEAD + COMMAND)
                done.append("Claude Code")
            except (OSError, ValueError) as e:
                problems.append(f"Claude Code: {e}")
    if "desktop" in targets:
        desk = desktop_configs()
        if not desk:
            problems.append("Claude Desktop isn't installed on this PC.")
        for p in desk:
            try:
                _edit(p, lambda d: d.setdefault("mcpServers", {}).__setitem__(NAME, _entry()))
                if "Claude Desktop" not in done:
                    done.append("Claude Desktop")
            except (OSError, ValueError) as e:
                problems.append(f"Claude Desktop ({p}): {e}")
    return {"done": done, "problems": problems, **status()}


def disconnect(targets=("code", "desktop")):
    def drop(d):
        if NAME not in (d.get("mcpServers") or {}):
            return False
        del d["mcpServers"][NAME]

    problems = []
    if "code" in targets:
        try:
            if not _run_cli("mcp", "remove", NAME, "--scope", "user"):
                _edit(code_config(), drop)
            f = command_file()
            if os.path.exists(f):
                with open(f, encoding="utf-8") as fh:
                    ours = MARK in fh.read()
                if ours:                              # only remove the command if BlockForge wrote it
                    os.remove(f)
        except (OSError, ValueError) as e:
            problems.append(f"Claude Code: {e}")
    if "desktop" in targets:
        for p in desktop_configs():
            try:
                _edit(p, drop)
            except (OSError, ValueError) as e:
                problems.append(f"Claude Desktop: {e}")
    return {"problems": problems, **status()}
