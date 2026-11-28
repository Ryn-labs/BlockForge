"""BlockForge MCP server (stdio). Lets a Claude Code chat create, edit and export builds that show up
in the BlockForge app's gallery. No extra packages needed."""
import base64
import inspect
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blockforge import blockinfo, exporters, learn, lessons, mods, patterns, placement, prompts, quality, sandbox, selfimprove, session, share, store, testlab  # noqa: E402

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
        "name": "block_info",
        "description": 'Facts about block states (solid or not, what it needs to stay in place, light, settable properties). Use it when unsure about a block, e.g. ["oak_stairs[facing=north,half=bottom]", "lantern[hanging=true]"].',
        "inputSchema": {"type": "object", "properties": {"blocks": {"type": "array", "items": {"type": "string"}, "description": "Block states"}}, "required": ["blocks"], "additionalProperties": False},
    },
    {
        "name": "style_sheet",
        "description": 'The style sheet (palette, shapes, details, mistakes) for a building style. Unknown or empty style lists the available styles.',
        "inputSchema": {"type": "object", "properties": {"style": {"type": "string"}}, "additionalProperties": False},
    },
    {
        "name": "lessons",
        "description": 'The top lessons learned from earlier builds. Read them before you build.',
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "pattern",
        "description": 'A proven build part as buildkit text (every pattern is also a function you can call by name directly in build_step / create_build code, e.g. manor_layout(0, 2, 0)): a whole manor (manor_layout: tall central block with a front gable, stepped wings, grand stair), house parts (framed_house, bay_window, dormer, framed_wall, window_with_box, porch, balcony, gable_roof_trim, hip_roof_trim, cross_gable_roof, chimney, stilt_base, fence_garden, farm_plot, site, road, plaza) and stairs, landings, doorway, lantern post, bridge, tree, spiral stairs. Unknown or empty name lists the patterns with their arguments.',
        "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "args": {"type": "object", "description": "Keyword arguments of the pattern, e.g. {\"x\": 3, \"y\": 1, \"z\": 4, \"facing\": \"south\"}"}}, "additionalProperties": False},
    },
    {
        "name": "start_build",
        "description": 'Start a step-by-step build session (the build lives on the server until save_build). Returns the session id. Read get_build_guide first. For a build ON real land pass terrain: the session then starts with that land (marked as terrain; every change to it is counted).',
        "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "size_hint": {"type": "string", "description": "Rough size or idea, e.g. 24 x 16 x 30 cottage"}, "terrain": {"type": "string", "description": "Optional: the id of a stored build (e.g. an imported .schem of the site) or the path of a .schem/.litematic file to build on"}}, "required": ["title"], "additionalProperties": False},
    },
    {
        "name": "build_step",
        "description": 'Run a SHORT buildkit snippet on top of what is already in the session (same functions as create_build scripts, coordinates x east, y up, z south). Returns blocks added/replaced/removed, overwrites, placement warnings and the build checks with coordinates. Build one part at a time, then view and check.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "code": {"type": "string", "description": "Build script for this part only"}, "note": {"type": "string", "description": "What this step is, e.g. north wall"}, "parts": {"type": "array", "maxItems": 12, "items": {"type": "object", "properties": {"note": {"type": "string"}, "code": {"type": "string"}}, "required": ["code"]}, "description": "Instead of code: several INDEPENDENT snippets (houses of one street, towers of one wall) run in parallel (4 at a time) on the current build and merged. If two parts change the same block the first one wins and the clash is reported. Then view and check once."}}, "required": ["session"], "additionalProperties": False},
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
        "name": "ground",
        "description": 'The ground height map of the build (y of the top solid block of every column, trees skipped) as rows of numbers, max 64 x 64 cells (a bigger area is sampled with a step). Use it before placing anything on terrain so the building sits ON the land. Without an area it covers everything.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "x1": {"type": "integer"}, "z1": {"type": "integer"}, "x2": {"type": "integer"}, "z2": {"type": "integer"}, "step": {"type": "integer", "description": "Sample every n blocks (default: as small as fits 64 cells)"}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "plan_layout",
        "description": 'Plan a whole district on the ground: finds the flattest free spot for every part (castle on high ground, plaza in the middle, houses near what they say), keeps 3+ blocks between them and joins them with streets that follow the ground with at most a 1 in 2 slope and flat landings at corners. Returns every part rectangle with its ground level and cut/fill, and every street centre line as (x,z,y) points. Build part by part from the plan (pass the street points to stair/path patterns).',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "area": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4, "description": "[x1, z1, x2, z2] to plan inside"}, "parts": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "w": {"type": "integer", "description": "size along x"}, "l": {"type": "integer", "description": "size along z"}, "kind": {"type": "string", "enum": ["house", "plaza", "castle", "shrine", "park"]}, "near": {"type": "string", "description": "name of another part to sit close to"}}, "required": ["name", "w", "l", "kind"]}}, "street_width": {"type": "integer", "default": 5}}, "required": ["session", "area", "parts"], "additionalProperties": False},
    },
    {
        "name": "make_terrain",
        "description": 'Lay real-looking land into the session: a mountain (one massif with side peaks, ridges and gullies), a range, a valley with a river, or rolling hills. Smooth slopes (no steps over 3 except real cliffs), rock strata on steep faces, scree, snow above the snowline, trees that thin out with height, land that rolls out to the box edge. Use it for EVERY mountain, hill or valley (never cones, cylinders or stacked boxes), then build on it. Returns what changed and the terrain score.',
        "inputSchema": {"type": "object", "properties": {
            "session": {"type": "string", "description": "Session id from start_build"},
            "kind": {"type": "string", "enum": ["mountain", "range", "valley", "hills"], "default": "mountain"},
            "x1": {"type": "integer"}, "z1": {"type": "integer"}, "x2": {"type": "integer"}, "z2": {"type": "integer"},
            "y": {"type": "integer", "default": 0, "description": "Ground level at the box edges"},
            "height": {"type": "integer", "default": 40, "description": "Rise of the highest ground above y"},
            "seed": {"type": "integer", "default": 0, "description": "Another seed = another mountain of the same kind"},
            "snowline": {"type": "integer", "description": "y where snow starts (default: 72% up a mountain, none on hills)"},
            "river": {"type": "boolean", "description": "Winding river along the valley floor (default on for valley)"},
            "trees": {"type": "boolean", "default": True}},
            "required": ["session", "x1", "z1", "x2", "z2"], "additionalProperties": False},
    },
    {
        "name": "describe",
        "description": 'Text description of the build as it is now: size, materials with where they are, and top, front and side letter maps.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "save_build",
        "description": 'Finish: run the final placement pass and save the session as a build in the BlockForge gallery. Returns the build id and the 3D preview link (give it to the user exactly as returned).',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}, "title": {"type": "string"}, "accept_problems": {"type": "string", "description": "Only when check still finds problems you cannot fix: say why each one is fine. Without it, save_build refuses while check finds problems."}, "keep_terrain_user_answer": {"type": "string", "description": "Only after the user said to keep land that save_build called unnatural: their words."}, "keep_size_user_answer": {"type": "string", "description": "Only after the USER answered that the current size is fine: their words. The AI can not waive a size miss itself."}, "keep_quality_user_answer": {"type": "string", "description": "Only after the USER answered that a plain building is what they want: their words. The AI can not waive a low quality score itself."}}, "required": ["session"], "additionalProperties": False},
    },
    {
        "name": "review",
        "description": 'Look at the build like a judge before save_build: the four side views and the top as pictures, the quality score (facade depth, roof, massing, palette, detail, surroundings; streets, variety, open space, landmark, density for towns) with what to fix and where, and a rubric. Score yourself 1-5 per part and fix every part below 4.',
        "inputSchema": {"type": "object", "properties": {"session": {"type": "string", "description": "Session id from start_build"}}, "required": ["session"], "additionalProperties": False},
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


SESSION_TOOLS = ("block_info", "style_sheet", "lessons", "pattern", "start_build", "build_step", "make_terrain", "view", "check", "walk_test", "undo", "history", "ground", "plan_layout", "describe", "review", "save_build")


def _pattern_table():
    import inspect
    return {n: f for n, f in inspect.getmembers(patterns, inspect.isfunction)
            if not n.startswith("_") and f.__module__ == patterns.__name__}


def _pattern_list(table):
    return "\n".join(f"- {n}{inspect.signature(f)}: {(f.__doc__ or '').strip().splitlines()[0] if (f.__doc__ or '').strip() else ''}"
                     for n, f in sorted(table.items()))


def _review(s):
    """review(session): the side views and the top, the quality score with what to fix, and the rubric."""
    if not s.blocks:
        raise ToolError("The build is empty, there is nothing to review yet.")
    q = quality.score(quality.built_only(s.blocks, s.terrain_blocks), s.size_hint, s.title)
    if q["building"]:
        head = (f"Quality {quality.summary(q)}; save_build needs {quality.QUALITY_MIN} or more.\n"
                + "\n".join("- " + f for f in q["findings"][:12]))
        weak = "\n".join(f"- {quality.LABELS[k]} {v}/100: " + " ".join(fx[:2]) for k, v, fx in quality.weakest(q) if fx)
        head += ("\nFix first:\n" + weak) if weak else ""
    else:
        head = "Not a building (no closed room), so it has no quality score; still make it look good."
    out = [{"type": "text", "text": head + "\n\n" + quality.RUBRIC}]
    for side, png in session.view(s, ["north", "east", "south", "west", "top"]):
        out.append({"type": "text", "text": side + ":"})
        out.append({"type": "image", "data": base64.b64encode(png).decode("ascii"), "mimeType": "image/png"})
    out.append({"type": "text", "text": "Write your 1-5 score for each part, then fix every part below 4 with build_step "
                                        "before save_build."})
    return out


def _extra_call(name, args):
    if name == "block_info":
        blocks = args.get("blocks") or []
        if isinstance(blocks, str):
            blocks = [blocks]
        if not blocks:
            raise ToolError("block_info needs a list of block states.")
        out = []
        for b in blocks[:40]:
            d = blockinfo.info(b)
            bad = blockinfo.check_properties(b)
            out.append(f"{b}: {blockinfo.explain(b)} Shape {d['shape']}, solid {d['solid']}, needs {d['needs_support']}, light {d['light']}."
                       + (f" Not allowed here: {', '.join(bad)}." if bad else ""))
        return "\n".join(out)
    if name == "style_sheet":
        text = lessons.for_style(args.get("style"))
        return text or ("Unknown style. Available: " + ", ".join(lessons.styles()))
    if name == "lessons":
        return "\n".join("- " + ln for ln in lessons.top(40))
    table = _pattern_table()
    fn = table.get(str(args.get("name") or "").strip().lower())
    if not fn:
        return "Unknown pattern. Available patterns (pass the arguments as args):\n" + _pattern_list(table)
    try:
        return fn(**(args.get("args") or {}))
    except (TypeError, ValueError) as e:
        raise ToolError(f"pattern {fn.__name__}{inspect.signature(fn)}: {e}") from None


def _session_call(name, args):
    if name in ("block_info", "style_sheet", "lessons", "pattern"):
        return _extra_call(name, args)
    try:
        if name == "start_build":
            s = session.start(args.get("title"), args.get("size_hint"), args.get("terrain"))
            if s.terrain:
                from . import terrain as _tr
                return (f"Build session {s.id} started ('{s.title}') on terrain. "
                        + _tr.summary(s.blocks, s.terrain_blocks, _tr.ground_top(s.blocks, s.terrain_blocks))
                        + " The terrain keeps its own coordinates. Build one part at a time with build_step, view and check.")
            return (f"Build session {s.id} started ('{s.title}'). Build one part at a time with build_step, then view and "
                    f"check. Coordinates: x east, y up, z south; start at 0,0,0.")
        s = session.load(args.get("session"))
        if name == "build_step":
            if args.get("parts"):
                return session.step_parts(s, args["parts"], args.get("note"))
            if not str(args.get("code") or "").strip():
                raise ToolError("build_step needs some code (or parts).")
            return session.step(s, args["code"], args.get("note"))
        if name == "make_terrain":
            keys = ("x1", "z1", "x2", "z2", "y", "height", "kind", "seed", "snowline", "river", "trees")
            kw = ", ".join(f"{k}={args[k]!r}" for k in keys if args.get(k) is not None)
            from . import terrain_quality as _tq
            text = session.step(s, f"natural_terrain({kw})", args.get("note") or f"natural terrain ({args.get('kind', 'mountain')})")
            q = _tq.score(quality.built_only(s.blocks, s.terrain_blocks))
            return (text if isinstance(text, str) else json.dumps(text)) + "\nTerrain: " + _tq.summary(q)
        if name == "ground":
            return session.ground_text(s, args.get("x1"), args.get("z1"), args.get("x2"), args.get("z2"), args.get("step"))
        if name == "plan_layout":
            return session.plan_layout_text(s, args.get("area"), args.get("parts"), args.get("street_width", 5))[0]
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
        if name == "review":
            return _review(s)
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
            found = _ck.run(s.blocks, ground=s.ground())
            if found and not (args.get("accept_problems") or "").strip():      # the AI looks at its problems before it may finish
                raise ToolError("Not saved yet: check still finds problems. Fix them with build_step (look with view, test paths with walk_test), "
                                "then call save_build again. If one can't be fixed or is intended, call save_build with accept_problems "
                                "explaining why.\n" + session.check_text(s))
            size_msg = prompts.size_problem(s.size_hint, prompts.dims_of(s.blocks))
            user_ok = (args.get("keep_size_user_answer") or "").strip() and not os.environ.get("BLOCKFORGE_UNATTENDED")
            if size_msg and not user_ok:                                     # a size miss is never waived by the AI itself: fix it, or ask the user
                raise ToolError("Not saved yet: the size is off. " + size_msg + " Resize the build with build_step (scale the whole design, "
                                "keep the detail), then call save_build again. accept_problems does not cover the size. "
                                + ("" if os.environ.get("BLOCKFORGE_UNATTENDED") else "If you are talking with the user, ask them: keep this size or fix it to the target? "
                                   "Only if they say keep it, call save_build with keep_size_user_answer set to their words."))
            q = quality.score(quality.built_only(s.blocks, s.terrain_blocks), s.size_hint, s.title)
            unattended = bool(os.environ.get("BLOCKFORGE_UNATTENDED"))
            user_q = bool((args.get("keep_quality_user_answer") or "").strip()) and not unattended
            if q["building"] and q["total"] < quality.QUALITY_MIN and not user_q:   # a plain box is never waived by the AI itself
                raise ToolError("Not saved yet: the " + ("town" if q.get("town") else "building") + " looks too plain. "
                                + quality.gate_text(q) + "\nFix the weakest parts with build_step (pattern() has framed_house, "
                                "framed_wall, window_with_box, porch, balcony, storey_band, external_stair, gable_roof_trim, cross_gable_roof, "
                                "chimney, fence_garden, farm_plot, road, plaza), call review to look at it, then save_build again. accept_problems does not "
                                "cover the quality." + ("" if unattended else " If the user asked for a plain building on purpose, ask "
                                "them; only if they say keep it, call save_build with keep_quality_user_answer set to their words."))
            from . import terrain_quality as _tq                              # AI-made land must look like land, not a house
            built = quality.built_only(s.blocks, s.terrain_blocks)
            user_t = bool((args.get("keep_terrain_user_answer") or "").strip()) and not unattended
            if not q["building"] and _tq.is_terrain(built):
                tqs = _tq.score(built)
                if tqs["total"] < _tq.TERRAIN_MIN and not user_t:
                    raise ToolError("Not saved yet: " + _tq.gate_text(tqs) + " Rebuild the land with make_terrain (or "
                                    "natural_terrain in build_step), then save_build again. accept_problems does not cover the terrain."
                                    + ("" if unattended else " If the user asked for this land on purpose, ask them; only if they "
                                       "say keep it, call save_build with keep_terrain_user_answer set to their words."))
            m, link = session.save(s, args.get("title"))
            if q["building"]:
                m = store.update_meta(m["id"], quality={"total": q["total"], "parts": q["parts"], "town": q["town"],
                                                        "kept_by_user": user_q and q["total"] < quality.QUALITY_MIN})
            return _summary(m) + ("\nQuality: " + quality.summary(q) if q["building"] else "") + link
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
        try:                                                  # look at it like a reviewer would: checks + quality
            a = selfimprove.assess(blocks, prompt=prompt)
        except Exception:                                     # a broken look must never lose the saved build
            a = None
        bad = a and selfimprove.not_done_text(a, "build", f"update_build with build_id {m['id']} and ONLY the changes")
        if bad:
            return bad + "\n\n" + _summary(m) + lab_report
        return "Done. " + _summary(m) + lab_report + share.chat_text(m["id"])
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
