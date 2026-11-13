"""BlockForge MCP server (stdio). Lets a Claude Code chat create, edit and export builds that show up
in the BlockForge app's gallery. No extra packages needed."""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blockforge import exporters, learn, mods, placement, prompts, sandbox, store, testlab  # noqa: E402

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
        "name": "export_build",
        "description": "Export a build to a schematic file and return its path. Formats: schem (WorldEdit), "
                       "litematic (Litematica), nbt (structure block), mcstructure (Bedrock).",
        "inputSchema": {"type": "object", "properties": {
            "build_id": {"type": "string"},
            "format": {"type": "string", "enum": list(exporters.FORMATS)}},
            "required": ["build_id", "format"], "additionalProperties": False},
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
        return (guide + "\n" + brief + "\nPass the builds you studied to create_build as `references`.\n\n"
                + "If the request needs working redstone (doors, farms, sorters, contraptions):\n" + prompts.REDSTONE_GUIDE)
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
        return _summary(m) + lab_report
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
                                "then create_build. Builds appear in the user's BlockForge app. app_open opens the "
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
            text = call(p.get("name"), p.get("arguments") or {})
            return {"content": [{"type": "text", "text": text}]}
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
