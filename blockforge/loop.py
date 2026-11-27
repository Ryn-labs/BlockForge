"""The step-by-step build engine: Claude Code runs with BlockForge's own session tools (start_build, build_step, view,
check, walk_test, save_build) and builds one part at a time, looking at the result, instead of writing one blind script."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from . import store

PREFIX = "mcp__blockforge__"
TOOLS = ("block_info", "style_sheet", "lessons", "pattern", "start_build", "build_step", "view", "check", "walk_test", "undo", "history", "describe", "save_build",
         "get_build_guide")
TIMEOUT = 1200                  # seconds, same kill timer as the script path
MAX_TURNS = 80


def mcp_config(work):
    """Write the --mcp-config file that starts BlockForge's own MCP server with this data folder and port."""
    from . import claudelink
    cmd, args = claudelink.mcp_command()
    entry_args = list(args) if getattr(sys, "frozen", False) else ["-I", *args]
    env = {"BLOCKFORGE_DATA": store.DATA}
    if os.environ.get("BLOCKFORGE_PORT"):
        env["BLOCKFORGE_PORT"] = os.environ["BLOCKFORGE_PORT"]
    path = os.path.join(work, "mcp.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"mcpServers": {"blockforge": {"type": "stdio", "command": cmd, "args": entry_args, "env": env}}}, f)
    return path


def style_for(text):
    """The style sheet name the request (or its palette line) names first, or None."""
    from . import lessons
    best = None
    for name in lessons.styles():
        m = re.search(r"\b" + name.replace("_", "[ _-]") + r"\b", text or "", re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name)
    return best[1] if best else None


def system_prompt(text=None):
    from . import lessons, mcp_server
    out = (mcp_server._skill_text() + "\n\n---\n\nYou have only the BlockForge session tools (and Read for a reference "
           "image). Write build scripts for build_step as described above; the script functions are the same in every step.\n")
    top = lessons.for_ai()
    if top:
        out += "\n## Lessons from earlier builds\n" + "\n".join(top) + "\n"
    style = style_for(text)
    if style:
        out += f"\n## Style sheet: {style}\n" + lessons.for_style(style).strip() + "\n"
    return out


def user_text(text):
    """text = prompts.user_message(...) (request, size, palette, version, mods...). Adds the instructions for the loop."""
    return (text + "\n\n## How to work\n"
            "Do not write one big script. Start with start_build (give it a title and the size). Plan the build in parts, then for "
            "each part: build_step it (about 10-40 lines), view it, and check it. Fix every problem the check lists with "
            "another build_step (or undo and redo the part). When paths, stairs or doors exist, walk_test the routes people "
            "will use and fix what it finds. Keep the overall size asked for. Finish with save_build and tell the user the "
            "preview link exactly as returned.")


def _describe(name, inp):
    name = name.replace(PREFIX, "")
    if name == "start_build":
        return "Starting the build: " + str(inp.get("title") or "")[:60]
    if name == "build_step":
        return "Building part: " + str(inp.get("note") or "next part")[:80]
    if name == "view":
        return "Looking at the build"
    if name == "check":
        return "Checking the build"
    if name == "walk_test":
        return "Walking the paths"
    if name == "undo":
        return "Taking a step back"
    if name == "save_build":
        return "Saving the build"
    if name in ("history", "describe", "get_build_guide"):
        return None
    if name == "Read":
        return "Looking at your reference image"
    return "Using " + name


def _text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")


def _spawn(cmd, work, env):
    err = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, cwd=work, env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc.err_file = err
    return proc


def newest_build(since):
    """The newest claude_chat build saved after `since` (fallback when the tool result can't be read)."""
    best = None
    for b in store.list_builds():
        if b.get("source") == "claude_chat" and b.get("created", 0) >= since - 1 and (not best or b["created"] > best["created"]):
            best = b
    return best


def run(text, model, usage, exe, log=print, image_path=None):
    """Run the loop. Returns the id of the build that save_build stored. Raises engine.EngineError."""
    from .engine import EngineError
    work = tempfile.mkdtemp(prefix="blockforge_loop_")
    started = time.time()
    try:
        if image_path:
            shutil.copy(image_path, work)
            text += (f"\n\nThe reference image is the file {os.path.basename(image_path)} in the current folder - "
                     "use the Read tool to look at it first.")
        allowed = ",".join([PREFIX + t for t in TOOLS] + ["Read"])
        cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--model", model,
               "--system-prompt", system_prompt(text), "--mcp-config", mcp_config(work), "--strict-mcp-config",
               "--tools", "Read", "--allowedTools", allowed, "--disallowedTools", ",".join(PREFIX + t for t in ("create_build", "update_build", "app_open", "app_close", "export_build")), "--max-turns", str(MAX_TURNS), "--no-session-persistence"]
        log("Asking Claude to build it step by step (via Claude Code)...")
        proc = _spawn(cmd, work, dict(os.environ))
        proc.stdin.write(user_text(text).encode("utf-8"))
        proc.stdin.close()
        timer = threading.Timer(TIMEOUT, proc.kill)
        timer.start()
        res, uses, saved_id, sid = None, {}, None, None
        try:
            for raw in proc.stdout:
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                kind = ev.get("type")
                if not isinstance(ev, dict): continue
                msg = ev.get("message")
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list): content = None
                if kind == "assistant":
                    for c in [x for x in (content or []) if isinstance(x, dict)]:
                        if c.get("type") == "tool_use":
                            uses[c.get("id")] = c.get("name", "")
                            line = _describe(c.get("name", ""), c.get("input") or {})
                            if line:
                                log(line)
                elif kind == "user" and isinstance(content, list):
                    for c in content:
                        if c.get("type") != "tool_result":
                            continue
                        name = uses.get(c.get("tool_use_id"), "").replace(PREFIX, "")
                        out = _text_of(c.get("content"))
                        if name == "start_build" and not c.get("is_error"):
                            m0 = re.search(r"session (\S+) started", out)
                            sid = m0.group(1) if m0 else sid
                        if c.get("is_error") and name == "save_build":
                            log("Save refused: " + out[:160].replace(chr(10), " "))
                        if name == "check":
                            m = re.search(r"(\d+) problem", out)
                            log("Checks: " + (f"{m.group(1)} problems" if m else "no problems"))
                        elif name == "save_build" and not c.get("is_error"):
                            m = re.search(r"\(id ([\w-]+)\)", out)
                            if m:
                                saved_id = m.group(1)
                        elif c.get("is_error") and name == "build_step":
                            log("A step failed and changed nothing: " + out[:120].replace("\n", " "))
                elif kind == "result":
                    res = ev
            proc.wait()
        finally:
            timer.cancel()
        if res is None:
            proc.err_file.seek(0)
            err = proc.err_file.read().decode("utf-8", "replace").strip()
            if "login" in err.lower() or "auth" in err.lower():
                raise EngineError("Claude Code isn't signed in. Open Settings and click 'Sign in to Claude'.")
            raise EngineError("Claude Code stopped without an answer. " + err[-600:])
        usage.add_claude_code(res, 0)
        if res.get("is_error") and not saved_id:
            msg = str(res.get("result") or res.get("error") or res)
            if "login" in msg.lower() or "/login" in msg:
                raise EngineError("Claude Code isn't signed in. Open Settings and click 'Sign in to Claude'.")
            if "limit" in msg.lower():
                raise EngineError("You've hit your Claude usage limit for now: " + msg[:300])
            raise EngineError("Claude returned an error: " + msg[:800])
        if not saved_id:
            b = newest_build(started)
            saved_id = b and b["id"]
        if not saved_id and sid:                                        # it built but never finished: save what it made, with its check results
            try:
                from . import session as _ss
                m_, _ = _ss.save(_ss.load(sid))
                saved_id = m_["id"]; log("Saved the build as it was (Claude stopped before save_build).")
            except Exception as e:
                log(f"Could not save the unfinished session {sid}: {e}")
        if not saved_id:
            raise EngineError("Claude finished without saving the build (it never called save_build).")
        return saved_id
    finally:
        shutil.rmtree(work, ignore_errors=True)
