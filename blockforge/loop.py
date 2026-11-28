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
TOOLS = ("block_info", "style_sheet", "lessons", "pattern", "start_build", "build_step", "view", "check", "walk_test", "undo", "history", "ground", "plan_layout", "describe", "review", "save_build",
         "get_build_guide")
TIMEOUT = 1200                  # seconds, same kill timer as the script path
MAX_TURNS = int(__import__("os").environ.get("BLOCKFORGE_MAX_TURNS", "200"))


def mcp_config(work):
    """Write the --mcp-config file that starts BlockForge's own MCP server with this data folder and port."""
    from . import claudelink
    cmd, args = claudelink.mcp_command()
    entry_args = list(args) if getattr(sys, "frozen", False) else ["-I", *args]
    env = {"BLOCKFORGE_DATA": store.DATA, "BLOCKFORGE_UNATTENDED": "1"}   # no user to ask: a size miss must be fixed
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


def user_text(text, session_id=None):
    """text = prompts.user_message(...) (request, size, palette, version, mods...). Adds the instructions for the loop.
    session_id = a session that already stands on the terrain (do not call start_build)."""
    if session_id:
        start = (f"Build session {session_id} is ALREADY started and holds the terrain: do not call start_build, pass "
                 f"session=\"{session_id}\" to every tool. Read its ground first (describe, ground), then plan_layout for whole "
                 "districts, and build part by part (build_step with parts for several independent houses at once) ON the land. ")
    else:
        start = "Start with start_build (give it a title and the size). "
    return (text + "\n\n## How to work\n"
            "Do not write one big script. " + start + "Plan the build in parts, then for "
            "each part: build_step it (about 10-40 lines), view it, and check it. Fix every problem the check lists with "
            "another build_step (or undo and redo the part). When paths, stairs or doors exist, walk_test the routes people "
            "will use and fix what it finds. Several houses (a street, a town, terraces): build them in ONE build_step "
            "with parts, one part per house (4 run at the same time), then view and check once - not one call per house. "
            "Keep the overall size asked for. For a house, building or town start from "
            "the proven pattern() parts (see 'Houses and towns'), never a bare box; a house by default has 2+ storeys, "
            "the light reference palette (birch, oak or stripped wood fill in an oak or spruce log frame, a teal or "
            "colored layered roof with an oak trim, big white-framed windows, a planter of soft mixed plants under every second lower window, never red flowers under every window) and a "
            "balcony; dark oak, deepslate or blackstone and black roofs only if the request asks for a dark look. "
            "Big houses: central tall block + front gable, stepped wings, varied roof heights, no wall run over 9 "
            "blocks; call manor_layout(x, y, z, facing) (and every pattern) directly in build_step code. Windows are clear glass_pane in a light frame, flowers only in a box under them. "
            "Before save_build call review and fix "
            "every part you score below 4. Finish with save_build and tell the user the preview link exactly as returned.")


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
    if name == "review":
        return "Reviewing how the build looks"
    if name == "save_build":
        return "Saving the build"
    if name == "ground":
        return "Reading the ground height"
    if name == "plan_layout":
        return "Planning the layout"
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


def newest_build(since, exclude=()):
    """The newest claude_chat build saved during this run (fallback when the tool result can't be read). Builds that existed
    before the run started are never picked, so a build made just before can't be mistaken for this one."""
    best = None
    for b in store.list_builds():
        if b["id"] in exclude: continue
        if b.get("source") == "claude_chat" and b.get("created", 0) >= since - 1 and (not best or b["created"] > best["created"]):
            best = b
    return best


def _look(sid):
    """Checks + quality of a build session now (None when it can't be read)."""
    from . import selfimprove, session as _ss
    try:
        s = _ss.load(sid)
        return selfimprove.assess(s.blocks, s.ground(), s.terrain_blocks, s.size_hint, prompt=s.title)
    except Exception:
        return None


def _improve(sid, request, turn, usage, log, started=None):
    """After the AI ended: up to LOOP_ROUNDS more turns while the session has check problems or low quality, within
    the time budget (selfimprove.LOOP_SECONDS from `started`): a round starts only with ROUND_MIN_SECONDS left and is
    stopped when the budget runs out (the session is saved as it is then)."""
    from . import selfimprove
    from .engine import EngineError
    n = selfimprove.LOOP_ROUNDS
    started = started or time.time()
    for k in range(1, n + 1):
        left = selfimprove.LOOP_SECONDS - (time.time() - started)
        if left < selfimprove.ROUND_MIN_SECONDS:
            log(f"No time left for improvement round {k} (the build has used {round((time.time() - started) / 60)} minutes).")
            return
        a = _look(sid)
        if a is None or a["ok"]:
            return
        log(selfimprove.status_line(a, k, n))
        msg = (f"Session id: {sid}\nThe build session already exists and holds the build for this request (shortened): "
               f"{request.strip()[:1200]}\n\n" + selfimprove.improve_message(a, k, n)
               + f"\n\nPass session=\"{sid}\" to every tool and do not call start_build. Fix, check until it says no problems, "
               "call review, then call save_build.")
        try:
            res = turn(msg, first=False, timeout=max(60, int(left)))
        except EngineError as e:
            log("Could not keep improving: " + str(e)[:160])
            return
        usage.add_claude_code(res, 0)


def run(text, model, usage, exe, log=print, image_path=None, terrain=None, title=None):
    """Run the loop. Returns the id of the build that save_build stored. Raises engine.EngineError.
    terrain = a build id or a .schem/.litematic path: the session is started on that land before the AI begins."""
    from .engine import EngineError
    work = tempfile.mkdtemp(prefix="blockforge_loop_")
    started = time.time()
    before = {b["id"] for b in store.list_builds()}
    try:
        pre = None
        if terrain:
            from . import session as _ss, terrain as _tr
            try:
                pre = _ss.start(str(title or "Build on terrain")[:80], "", terrain)
            except _ss.SessionError as e:
                raise EngineError("Could not start on that terrain: " + str(e)) from None
            text += ("\n\n## The terrain\n" + _tr.summary(pre.blocks, pre.terrain_blocks, _tr.ground_top(pre.blocks, pre.terrain_blocks))
                     + "\nThe land is already in the build (it is saved with it). Never rebuild it; cut and fill only where the "
                     "buildings and roads need it, and say how much.")
        if image_path:
            shutil.copy(image_path, work)
            text += (f"\n\nThe reference image is the file {os.path.basename(image_path)} in the current folder - "
                     "use the Read tool to look at it first.")
        allowed = ",".join([PREFIX + t for t in TOOLS] + ["Read"])
        cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--model", model,
               "--system-prompt", system_prompt(text), "--mcp-config", mcp_config(work), "--strict-mcp-config",
               "--tools", "Read", "--allowedTools", allowed, "--disallowedTools", ",".join(PREFIX + t for t in ("create_build", "update_build", "app_open", "app_close", "export_build")), "--max-turns", str(MAX_TURNS), "--no-session-persistence"]
        log("Asking Claude to build it step by step (via Claude Code)...")
        saved_id, sid = None, (pre.id if pre else None)

        def turn(message, first=True, timeout=None):
            """One claude -p run on the session tools; returns its result event (None when it stopped without one)."""
            nonlocal saved_id, sid
            proc = _spawn(cmd, work, dict(os.environ))
            proc.stdin.write(message.encode("utf-8"))
            proc.stdin.close()
            timer = threading.Timer(min(TIMEOUT, timeout or TIMEOUT), proc.kill)
            timer.start()
            res, uses = None, {}
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
                            if name == "start_build" and not c.get("is_error") and first:
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
            return res

        res = turn(user_text(text, pre.id if pre else None))
        usage.add_claude_code(res, 0)
        out_of_turns = res.get("subtype") == "error_max_turns"
        if out_of_turns and sid:                                       # the turn cap ends the conversation, not the build: keep and improve it
            log("Reached the step limit for one run; keeping the build and finishing it.")
        elif res.get("is_error") and not saved_id:
            msg = str(res.get("result") or res.get("error") or res.get("subtype") or "")
            low = msg.lower()
            if "login" in low or "/login" in msg:
                raise EngineError("Claude Code isn't signed in. Open Settings and click 'Sign in to Claude'.")
            if "usage limit" in low or "rate limit" in low or "limit will reset" in low or "limit reached" in low:
                raise EngineError("You've hit your Claude usage limit for now: " + msg[:300])
            raise EngineError("Claude returned an error: " + msg[:800])
        if sid:                                                         # check -> fix -> check until clean, before anything is saved
            first_saved = saved_id
            _improve(sid, text, turn, usage, log, started)
            if first_saved and saved_id != first_saved:                 # the improved build replaces the flawed one saved earlier in this run
                try:
                    store.delete_build(first_saved)
                except Exception:
                    pass
        if not saved_id:
            b = newest_build(started, before)
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
