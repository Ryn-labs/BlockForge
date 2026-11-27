"""BlockForge MCP server (stdio). Lets a Claude Code chat create, edit and export builds that show up
in the BlockForge app's gallery. No extra packages needed."""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blockforge import exporters, learn, mods, placement, prompts, sandbox, session, share, store, testlab  # noqa: E402

SERVER = {"name": "blockforge", "version": "1.1.0"}
APP_URL = f"http://127.0.0.1:{os.environ.get('BLOCKFORGE_PORT', '8765')}"

TOOLS = [
    {
        "name": "app_status",
        "description": "Is the BlockForge app open? Returns its version, the build on screen, whether it's busy "
                       "making a build, and how many builds are in the gallery.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "app_open",
        "description": "Open the BlockForge app (starts it if it's closed) and bring its window to the front. "
                       "Pass build_id to show that build in it.",
        "inputSchema": {"type": "object", "properties": {
            "build_id": {"type": "string", "description": "Optional build to show"}}, "additionalProperties": False},
    },
    {
        "name": "app_close",
        "description": "Close the BlockForge app window. Refuses while a build is being made unless force is true "
                       "(ask the user first).",
        "inputSchema": {"type": "object", "properties": {
            "force": {"type": "boolean", "default": False}}, "additionalProperties": False},
    },
    {
        "name": "get_build_guide",
        "description": "Read this FIRST before writing a BlockForge build script: the build toolkit "
                       "(fill, walls, gable_roof, sphere, ...), block-state rules and the quality checklist.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "create_build",
        "description": "Run a BlockForge Python build script and save the result as a new Minecraft build in the "
                       "user's BlockForge gallery (it appears in the app automatically). Returns the build id, "
                       "size, block count and exported .schem/.litematic file paths. If the script fails, the error "
                       "is returned so you can fix it and call again.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short name for the build"},
                "code": {"type": "string", "description": "The complete build script"},
                "prompt": {"type": "string", "description": "What the user asked for (shown in the app)"},
                "references": {"type": "array", "description": "Real builds you studied first (shown as Sources)",
                               "items": {"type": "object", "properties": {
                                   "title": {"type": "string"}, "url": {"type": "string"}, "site": {"type": "string"},
                                   "size": {"type": "string"}, "takeaways": {"type": "string"}}}},
            },
            "required": ["title", "code"], "additionalProperties": False,
        },
    },
    {
        "name": "update_build",
        "description": "Make a new version of an existing build from an edited script (the original is kept). "
                       "Use get_build first to read the current script.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "build_id": {"type": "string"},
                "code": {"type": "string", "description": "The complete updated script"},
                "change": {"type": "string", "description": "What was changed"},
                "title": {"type": "string"},
            },
            "required": ["build_id", "code"], "additionalProperties": False,
        },
    },
    {
        "name": "list_builds",
        "description": "List builds in the BlockForge gallery (newest first).",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Optional text filter"},
            "limit": {"type": "integer", "default": 20}}, "additionalProperties": False},
    },
    {
        "name": "get_build",
        "description": "Get a build's details, material list and its build script.",
        "inputSchema": {"type": "object", "properties": {"build_id": {"type": "string"}},
                        "required": ["build_id"], "additionalProperties": False},
    },
    {
        "name": "preview_link",
        "description": "Get a link to a 3D preview of a build that anyone can open in a web browser (rotate, zoom, "
                       "see inside layer by layer). Give it to the user exactly as returned.",
        "inputSchema": {"type": "object", "properties": {"build_id": {"type": "string"}},
                        "required": ["build_id"], "additionalProperties": False},
    },
    {
        "name": "export_build",
        "description": "Export a build to a schematic file and return its path. Formats: schem (WorldEdit), "
                       "litematic (Litematica), nbt (structure block), mcstructure (Bedrock).",
        "inputSchema": {"type": "object", "properties": {
            "build_id": {"type": "string"},
            "format": {"type": "string", "enum": list(exporters.FORMATS)}},
            "required": ["build_id", "format"], "additionalProperties": False},
    },
    {
        "name": "start_build",
        "description": 'Start a step-by-step build session (the build lives on the server until save_build). Returns the session id. Read get_build_guide first.',
        "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "size_hint": {"type": "string", "description": "Rough size or idea, e.g. 24 x 16 x 30 cottage"}}, "required": ["title"], "additionalProperties": False},
    },
    {
        "name": "build_step",
        "description": 'Run a SHORT buildkit snippet on top of what is already in the session (same functions as create_build scripts, coordinates x east, y up, z south). Returns blocks added/replaced/removed, overwrites, placement warnings and the build checks with coordinates. Build one part at a time, then view and check.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "code": {"type": "string", "description": "Build script for this part only"}, "note": {"type": "string", "description": "What this step is, e.g. north wall"}}, "required": ["session", "code"], "additionalProperties": False},
    },
    {
        "name": "view",
        "description": 'Look at the build: flat elevations (north, east, south, west, top) as pictures, nearest block per column, darker when further back. Use it after every part.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "sides": {"type": "array", "items": {"type": "string", "enum": ["north", "east", "south", "west", "top"]}, "description": "Default: all five"}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "check",
        "description": 'Run all build checks (floating parts, buried or jumpy paths, wrong stair facing, corner turns, blocked doors, head room) and list every problem with coordinates.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "walk_test",
        "description": 'Walk a path through the build and report jumps over 0.6 of a block, blocked head room (less than 2 free blocks) and missing floor, each with coordinates.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "path": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}, "description": "Points [x, z] to walk between in order, e.g. [[2, 12], [2, 5], [9, 5]]"}}, "required": ["session", "path"], "additionalProperties": False},
    },
    {
        "name": "undo",
        "description": 'Undo the last step(s) of the session.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "steps": {"type": "integer", "default": 1}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "history",
        "description": 'List the steps done so far in the session.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "describe",
        "description": 'Text description of the build as it is now: size, materials with where they are, and top, front and side letter maps.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "save_build",
        "description": 'Finish: run the final placement pass and save the session as a build in the BlockForge gallery. Returns the build id and the 3D preview link (give it to the user exactly as returned).',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "title": {"type": "string"}, "accept_problems": {"type": "string", "description": "Only when check still finds problems you cannot fix: say why each one is fine. Without it, save_build refuses while check finds problems."}}, "required": ["session"], "additionalProperties": False},
    },
]


def _summary(meta):
    paths = {f: store.export_path(meta["id"], f) for f in ("schem", "litematic")}
    mats = ", ".join(f"{n} x{c}" for n, c in meta.get("materials", [])[:8])
    return (f"Saved build '{meta['title']}' (id {meta['id']}).\n"
            f"Size {meta['size'][0]} x {meta['size'][1]} x {meta['size'][2]} (W x H x L), "
            f"{meta['block_count']:,} blocks.\nTop materials: {mats}\n"
            f"Files:\n  {paths['schem']}\n  {paths['litematic']}\n"
            f"It is now in the BlockForge gallery ({APP_URL})."
            + ("\n\nBlockForge auto-fixed these so every block can exist in vanilla:\n- " + "\n- ".join(meta["fixes"])
               if meta.get("fixes") else "")
            + ("\n\nRedstone checker found problems (fix them with update_build):\n- " + "\n- ".join(meta["warnings"])
               if meta.get("warnings") else ""))


# ------------------------------------------------------------------ the app window
def _api(path, body=None, timeout=10):
    """Talk to the running app. Returns (status, json), or (None, None) if it isn't running."""
    req = urllib.request.Request(APP_URL + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (OSError, ValueError):
        return None, None


def _app_command():
    """How to start the app: the installed BlockForge.exe if there is one, else from source."""
    if getattr(sys, "frozen", False):
        exe = os.path.join(os.path.dirname(sys.executable), "BlockForge.exe")
        if os.path.exists(exe):
            return [exe]
    exe = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "BlockForge", "BlockForge.exe")
    if os.path.exists(exe) and not os.environ.get("BLOCKFORGE_DATA"):   # a test data folder means: run this source
        return [exe]
    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
    return [pyw if os.path.exists(pyw) else py, os.path.join(os.path.dirname(os.path.abspath(__file__)), "launcher.pyw")]


def _launch():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("_MEI", "_PYI"))}   # don't confuse another frozen exe
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(_app_command(), env=env, creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _describe(st):
    cur = st.get("current")
    return (f"BlockForge {st.get('version')} is open"
            + (f", showing '{cur['title']}' (id {cur['id']})" if cur else ", no build open")
            + (f", busy making {st['busy']} build(s)" if st.get("busy") else "")
            + f". {st.get('builds', 0)} builds in the gallery.")


def app_status():
    code, st = _api("/api/app")
    if code is None:
        return "BlockForge is closed."
    if code != 200:
        return "BlockForge is running, but it's an older version that can't report its status. Update it."
    if not st.get("window"):
        return "BlockForge's server is running without a window (developer mode)."
    return _describe(st)


def app_open(build_id=None):
    if build_id:
        try:
            store.get_meta(build_id)
        except (KeyError, OSError, ValueError):
            raise ToolError(f"There's no build with id {build_id}. Use list_builds to find it.") from None
    started = False
    code, st = _api("/api/app")
    if code is None:
        _launch()
        started = True
        for _ in range(120):                          # up to ~60 s for the first start after an install
            time.sleep(0.5)
            code, st = _api("/api/app", timeout=3)
            if code == 200 and st.get("ready"):
                break
        else:
            raise ToolError("BlockForge was started but didn't answer within a minute. It may still be loading.")
    elif code != 200:
        raise ToolError("BlockForge is running, but it's an older version that can't be controlled. Update it.")
    code, st = _api("/api/app/show", {"build_id": build_id} if build_id else {})
    if code != 200:
        raise ToolError((st or {}).get("error") or "Couldn't bring BlockForge to the front.")
    if build_id:
        for _ in range(20):                           # wait for the build to load in the window
            time.sleep(0.25)
            st = _api("/api/app")[1] or st
            if (st.get("current") or {}).get("id") == build_id:
                break
    return ("Started BlockForge. " if started else "") + _describe(st)


def app_close(force=False):
    code, st = _api("/api/app/quit", {"force": bool(force)})
    if code is None:
        return "BlockForge is already closed."
    if code == 409:
        raise ToolError((st or {}).get("error") or "BlockForge can't be closed right now.")
    if code != 200:
        raise ToolError("BlockForge is running, but it's an older version that can't be closed from here.")
    for _ in range(20):
        time.sleep(0.25)
        if _api("/api/app", timeout=1)[0] is None:
            return "Closed BlockForge."
    return "Asked BlockForge to close."


PROMPTS = [{
    "name": "blockforge",
    "title": "BlockForge",
    "description": "Open or close BlockForge, show a build, or make a new Minecraft build",
    "arguments": [{"name": "request", "description": "open, close, status, show <build>, or what to build",
                   "required": False}],
}]


def get_prompt(name, args):
    if name != "blockforge":
        raise LookupError(name)
    from blockforge import claudelink
    text = claudelink.COMMAND.replace(claudelink.MARK, "").strip().replace("$ARGUMENTS", (args or {}).get("request") or "open")
    return {"description": PROMPTS[0]["description"],
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}


def _skill_text():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SKILL.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


SESSION_TOOLS = ("start_build", "build_step", "view", "check", "walk_test", "undo", "history", "describe", "save_build")


def _session_call(name, args):
    try:
        if name == "start_build":
            s = session.start(args.get("title"), args.get("size_hint"))
            return (f"Build session {s.id} started ('{s.title}'). Build one part at a time with build_step, then view and "
                    f"check. Coordinates: x east, y up, z south; start at 0,0,0.")
        s = session.load(args.get("session"))
        if name == "build_step":
            if not str(args.get("code") or "").strip():
                raise ToolError("build_step needs some code.")
            return session.step(s, args["code"], args.get("note"))
        if name == "view":
            pics = session.view(s, args.get("sides"))
            out = [{"type": "text", "text": f"{len(s.blocks):,} blocks. Views: " + ", ".join(p[0] for p in pics)
                    + ". Each picture is the nearest block in every column; darker means further back."}]
            for side, png in pics:
                out.append({"type": "text", "text": side + ":"})
                out.append({"type": "image", "data": base64.b64encode(png).decode("ascii"), "mimeType": "image/png"})
            return out
        if name == "check":
            return session.check_text(s)
        if name == "walk_test":
            return session.walk(s, args.get("path"))
        if name == "undo":
            return session.undo(s, args.get("steps", 1))
        if name == "history":
            return session.history_text(s)
        if name == "describe":
            return session.describe_text(s)
        if name == "save_build":
            from . import checks as _ck
            found = _ck.run(s.blocks)
            if found and not (args.get("accept_problems") or "").strip():      # the AI looks at its problems before it may finish
                raise ToolError("Not saved yet: check still finds problems. Fix them with build_step (look with view, test paths with walk_test), "
                                "then call save_build again. If one can't be fixed or is intended, call save_build with accept_problems "
                                "explaining why.\n" + session.check_text(s))
            m, link = session.save(s, args.get("title"))
            return _summary(m) + link
    except session.SessionError as e:
        raise ToolError(str(e)) from None
    raise ToolError("Unknown tool " + name)


def call(name, args):
    if name == "app_status":
        return app_status()
    if name == "app_open":
        return app_open(args.get("build_id"))
    if name == "app_close":
        return app_close(args.get("force"))
    if name == "get_build_guide":
        guide = prompts.SYSTEM.replace("Reply with a one-line title, then ONE ```python code block. No other prose is needed.",
                                       "Pass your script to the create_build tool.")
        sites = store.load_settings().get("research_sites") or prompts.DEFAULT_SITES
        brief = prompts.research_brief(sites).split("Your reply must contain")[0]
        skill = _skill_text()
        return ((skill + "\n\n---\n\nThe older whole-script guide follows. It still applies to create_build.\n\n" if skill else "")
                + guide + "\n" + brief + "\nPass the builds you studied to create_build as `references`.\n\n"
                + "If the request needs working redstone (doors, farms, sorters, contraptions):\n" + prompts.REDSTONE_GUIDE)
    if name in SESSION_TOOLS:
        return _session_call(name, args)
    if name in ("create_build", "update_build"):
        parent = args.get("build_id")
        if parent:
            store.get_meta(parent)
        try:
            pack, version, popts = mods.build_opts()
            base_id, base = store.edit_base(parent) if parent else (None, None)
            blocks, meta = sandbox.run_safe(args["code"], placement_opts=popts, base=base)
        except sandbox.ScriptError as e:
            raise ToolError("The build script failed:\n" + str(e))
        final = placement.process(blocks, final=True, **popts, only=sandbox.scope(meta))   # nothing impossible gets saved
        sandbox.restore_modules(blocks, meta)
        if base:
            sandbox.protect_base(blocks, meta, base[0])
        fixes = (meta.get("fixes") or []) + final["fixed"]
        tested, lab_report = None, ""
        if meta.get("tests") and testlab.status()["enabled"]:
            try:
                res = testlab.run_test(blocks, sandbox.tiles_of(meta), meta.get("entities"), meta["tests"], lambda m: None)
                tested = {"passed": res["passed"], "version": res.get("version"),
                          "results": [r["text"] for r in res["results"] if r["ok"] is not None][:20], "attempts": 1}
                lab_report = "\n\nIn-game test (BlockForge test lab):\n" + res["report"] + (
                    "" if res["passed"] else "\nFix the design and call update_build until the test passes.")
            except (testlab.LabError, OSError) as e:
                lab_report = f"\n\nThe test lab couldn't run the test: {e}"
        elif prompts.wants_redstone(args.get("prompt") or "", args["code"]) and not meta.get("tests"):
            lab_report = "\n\nThis build has redstone but no test_* steps, so it was not proven to work in game."
        title = args.get("title") or meta.get("name") or (store.get_meta(parent)["title"] + " v2" if parent else "Build")
        prompt = args.get("prompt") or args.get("change") or ""
        refs = [{k: str(r.get(k, ""))[:300] for k in ("title", "url", "site", "size", "takeaways")}
                for r in args.get("references") or [] if isinstance(r, dict) and str(r.get("url", "")).startswith("http")]
        m = store.save_build(blocks, title, prompt=prompt, code=args["code"], source="claude_chat", parent=parent,
                             model="claude-code-chat", description=meta.get("description") or "",
                             references=refs[:10], researched=bool(refs),
                             redstone=prompts.wants_redstone(prompt, args["code"]),
                             warnings=meta.get("redstone_warnings") or [], fixes=fixes,
                             data_version=mods.data_version(version), modpack=(pack or {}).get("name"),
                             tiles=sandbox.tiles_of(meta), modules=meta.get("modules"), base=base_id,
                             entities=meta.get("entities"), tested=tested)
        learn.log_generation(m, fixes, meta.get("redstone_warnings") or [])
        return _summary(m) + lab_report + share.chat_text(m["id"])
    if name == "list_builds":
        q = (args.get("query") or "").lower()
        items = [b for b in store.list_builds() if not q or q in (b["title"] + " " + b.get("prompt", "")).lower()]
        items = items[: int(args.get("limit") or 20)]
        if not items:
            return "No builds yet."
        return "\n".join(f"{b['id']}  {b['title']}  ({'x'.join(map(str, b['size']))}, {b['block_count']:,} blocks, "
                         f"{b['source']}{', has script' if b.get('has_code') else ''})" for b in items)
    if name == "get_build":
        m = store.get_meta(args["build_id"])
        code = store.get_code(args["build_id"])
        mats = ", ".join(f"{n} x{c}" for n, c in m.get("materials", [])[:30])
        head = (f"{m['title']} (id {m['id']})\nPrompt: {m.get('prompt') or '-'}\n"
                f"Size {m['size']}, {m['block_count']:,} blocks\nMaterials: {mats}\n\n")
        base_id, base = store.edit_base(args["build_id"])
        if base:
            from blockforge import describe
            return (head + describe.base_brief(base[0], has_picture=False) +
                    "\n\nTo change it, call update_build with build_id and a script of ONLY the changes"
                    + (f". Current script of changes:\n```python\n{code}\n```" if code else "."))
        return head + "Script:\n```python\n" + (code or "") + "\n```"
    if name == "preview_link":
        store.get_meta(args["build_id"])
        return share.chat_text(args["build_id"]).strip()
    if name == "export_build":
        fmt = args["format"]
        if fmt not in exporters.FORMATS:
            raise ToolError("Unknown format " + fmt)
        return "Exported: " + store.export_path(args["build_id"], fmt)
    raise ToolError("Unknown tool " + name)


class ToolError(Exception):
    pass


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        ver = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        return {"protocolVersion": ver, "capabilities": {"tools": {}, "prompts": {}}, "serverInfo": SERVER,
                "instructions": "BlockForge makes Minecraft builds. Call get_build_guide before writing a script, "
                                "then build step by step (start_build, build_step, view, check, save_build) or write a whole script with "
                                "create_build. Builds appear in the user's BlockForge app. app_open opens the "
                                "app (and can show a build), app_close closes it, app_status says what it's doing."}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "prompts/list":
        return {"prompts": PROMPTS}
    if method == "prompts/get":
        p = msg.get("params") or {}
        return get_prompt(p.get("name"), p.get("arguments"))
    if method == "tools/call":
        p = msg.get("params") or {}
        try:
            res = call(p.get("name"), p.get("arguments") or {})
            return {"content": res if isinstance(res, list) else [{"type": "text", "text": res}]}
        except KeyError as e:
            return {"content": [{"type": "text", "text": f"Not found: {e}"}], "isError": True}
        except ToolError as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        except Exception as e:                       # noqa: BLE001
            return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
    if mid is None:
        return None                                  # notification
    raise LookupError(method)


def main():
    out = sys.stdout
    sys.stdout = sys.stderr
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        mid = msg.get("id")
        try:
            res = handle(msg)
            if mid is None:
                continue
            reply = {"jsonrpc": "2.0", "id": mid, "result": res}
        except LookupError as e:
            reply = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {e}"}}
        out.write(json.dumps(reply) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
