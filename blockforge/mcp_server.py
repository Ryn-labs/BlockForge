"""BlockForge MCP server (stdio). Lets a Claude Code chat create, edit and export builds that show up
in the BlockForge app's gallery. No extra packages needed."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blockforge import exporters, learn, mods, placement, prompts, sandbox, store  # noqa: E402

SERVER = {"name": "blockforge", "version": "1.0.0"}
APP_URL = "http://127.0.0.1:8765"

TOOLS = [
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


def call(name, args):
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
            blocks, meta = sandbox.run_safe(args["code"], placement_opts=popts)
        except sandbox.ScriptError as e:
            raise ToolError("The build script failed:\n" + str(e))
        final = placement.process(blocks, final=True, **popts)          # nothing impossible gets saved
        fixes = (meta.get("fixes") or []) + final["fixed"]
        title = args.get("title") or meta.get("name") or (store.get_meta(parent)["title"] + " v2" if parent else "Build")
        prompt = args.get("prompt") or args.get("change") or ""
        refs = [{k: str(r.get(k, ""))[:300] for k in ("title", "url", "site", "size", "takeaways")}
                for r in args.get("references") or [] if isinstance(r, dict) and str(r.get("url", "")).startswith("http")]
        m = store.save_build(blocks, title, prompt=prompt, code=args["code"], source="claude_chat", parent=parent,
                             model="claude-code-chat", description=meta.get("description") or "",
                             references=refs[:10], researched=bool(refs),
                             redstone=prompts.wants_redstone(prompt, args["code"]),
                             warnings=meta.get("redstone_warnings") or [], fixes=fixes,
                             data_version=mods.data_version(version), modpack=(pack or {}).get("name"))
        learn.log_generation(m, fixes, meta.get("redstone_warnings") or [])
        return _summary(m)
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
        return (f"{m['title']} (id {m['id']})\nPrompt: {m.get('prompt') or '-'}\n"
                f"Size {m['size']}, {m['block_count']:,} blocks\nMaterials: {mats}\n\n"
                + ("Script:\n```python\n" + code + "\n```" if code else "(imported file - no script)"))
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
        return {"protocolVersion": ver, "capabilities": {"tools": {}}, "serverInfo": SERVER,
                "instructions": "BlockForge makes Minecraft builds. Call get_build_guide before writing a script, "
                                "then create_build. Builds appear in the user's BlockForge app."}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
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
