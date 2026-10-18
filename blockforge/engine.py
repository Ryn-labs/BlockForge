"""Talk to Claude. Two ways in:
  - claude_code: the Claude Code program on this PC, signed in with your Claude account (no API key)
  - api:         the Anthropic API with your own API key
"""
import base64
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

from . import prompts, sandbox, store

MODELS = {
    "claude-opus-5-5": "Pro - Claude Opus 5.5 (best detail)",
    "claude-sonnet-5-5": "Standard - Claude Sonnet 5.5 (faster)",
    "claude-haiku-5-5": "Quick - Claude Haiku 5.5 (fastest)",
}
MAX_FIX_ATTEMPTS = 2


class EngineError(Exception):
    pass


# ------------------------------------------------------------------ Claude Code program
_found = {}


def _version(exe):
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", r.stdout.decode("utf-8", "replace"))
        return tuple(map(int, m.groups())) if m else (0,)
    except Exception:                                # noqa: BLE001
        return (0,)


def find_claude():
    """The newest Claude Code on this PC (standalone install or the one bundled with the desktop app)."""
    cands = [shutil.which("claude"), os.path.expanduser("~/.local/bin/claude.exe"),
             os.path.expanduser("~/.local/bin/claude")]
    cands += glob.glob(os.path.expandvars(r"%APPDATA%\Claude\claude-code\*\*\claude.exe"))
    cands = sorted({os.path.normcase(os.path.abspath(c)) for c in cands if c and os.path.isfile(c)})
    if not cands:
        return None
    key = tuple(cands)
    if key not in _found:
        _found[key] = max(cands, key=_version)
    return _found[key]


def claude_status():
    exe = find_claude()
    if not exe:
        return {"found": False, "logged_in": False}
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        info = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    except Exception as e:                           # noqa: BLE001
        return {"found": True, "path": exe, "logged_in": False, "error": str(e)}
    return {"found": True, "path": exe, "logged_in": bool(info.get("loggedIn")),
            "method": info.get("authMethod"), "account": info.get("email") or info.get("account")}


def open_claude_login():
    """Open a console window running `claude auth login` so the user can sign in."""
    exe = find_claude()
    if not exe:
        raise EngineError("Claude Code was not found on this PC.")
    subprocess.Popen(["cmd", "/c", "start", "Sign in to Claude", "cmd", "/k", exe, "auth", "login"])


# ------------------------------------------------------------------ usage tracking
PRICES = {  # USD per million tokens (input, output) - Anthropic list prices
    "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50),
}
WEB_SEARCH_USD = 0.01                                  # $10 per 1,000 searches


class Usage:
    """Adds up what Claude used for one generation (all fix attempts included)."""

    def __init__(self, engine, model):
        self.d = {"engine": engine, "model": model, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
                  "cache_write_tokens": 0, "thinking_tokens": 0, "web_searches": 0, "web_fetches": 0,
                  "turns": 0, "requests": 0, "cost_usd": 0.0, "seconds": 0.0}

    def add_claude_code(self, res, fetches):
        d = self.d
        d["requests"] += 1
        d["turns"] += res.get("num_turns") or 0
        d["seconds"] += (res.get("duration_ms") or 0) / 1000
        d["cost_usd"] += res.get("total_cost_usd") or 0
        d["web_fetches"] += fetches
        for mu in (res.get("modelUsage") or {}).values():
            cr, cw = mu.get("cacheReadInputTokens", 0), mu.get("cacheCreationInputTokens", 0)
            d["input_tokens"] += max(0, mu.get("inputTokens", 0) - cr - cw)
            d["cache_read_tokens"] += cr
            d["cache_write_tokens"] += cw
            d["output_tokens"] += mu.get("outputTokens", 0)
            d["thinking_tokens"] += mu.get("thinkingTokens", 0)
            d["web_searches"] += mu.get("webSearchRequests", 0)

    def add_api(self, u, model, seconds):
        d = self.d
        d["requests"] += 1
        d["turns"] += 1
        d["seconds"] += seconds
        inp, out = u.input_tokens or 0, u.output_tokens or 0
        cr, cw = getattr(u, "cache_read_input_tokens", 0) or 0, getattr(u, "cache_creation_input_tokens", 0) or 0
        stu = getattr(u, "server_tool_use", None)
        ws = (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
        wf = (getattr(stu, "web_fetch_requests", 0) or 0) if stu else 0
        d["input_tokens"] += inp
        d["output_tokens"] += out
        d["cache_read_tokens"] += cr
        d["cache_write_tokens"] += cw
        d["web_searches"] += ws
        d["web_fetches"] += wf
        pi, po = PRICES.get(model, PRICES["claude-opus-5-5"])
        d["cost_usd"] += (inp * pi + cr * pi * 0.1 + cw * pi * 1.25 + out * po) / 1e6 + ws * WEB_SEARCH_USD

    def record(self):
        r = dict(self.d)
        r["cost_usd"] = round(r["cost_usd"], 4)
        r["seconds"] = round(r["seconds"], 1)
        r["total_tokens"] = r["input_tokens"] + r["output_tokens"] + r["cache_read_tokens"] + r["cache_write_tokens"]
        r["billing"] = "Included in your Claude plan (cost shown at API list price)" if r["engine"] == "claude_code" \
            else "Charged to your API key"
        return r


def _short_url(u):
    u = re.sub(r"^https?://(www\.)?", "", u or "")
    return u if len(u) < 70 else u[:67] + "..."


def _describe_tool(name, inp):
    if name in ("WebSearch", "web_search"):
        doms = inp.get("allowed_domains") or []
        q = inp.get("query", "")
        m = re.search(r"site:(\S+)", q)
        where = (", ".join(doms) if len(doms) <= 2 else f"{len(doms)} schematic sites") if doms \
            else (m.group(1) if m else "the web")
        q = re.sub(r"site:\S+\s*", "", q).strip()
        return f'Searching {where} for "{q}"'
    if name in ("WebFetch", "web_fetch"):
        return "Reading " + _short_url(inp.get("url"))
    if name == "Read":
        return "Looking at your reference image"
    return f"Using {name}"


# ------------------------------------------------------------------ Claude Code program
def _ask_claude_code(text, model, usage, image_path=None, research=False, log=print):
    exe = find_claude()
    if not exe:
        raise EngineError("Claude Code isn't installed. Install it, or add an API key in Settings.")
    work = tempfile.mkdtemp(prefix="blockforge_")
    try:
        if image_path:
            shutil.copy(image_path, work)
            text += f"\n\nThe reference image is the file {os.path.basename(image_path)} in the current folder - " \
                    "use the Read tool to look at it first."
        tools = "Read,WebSearch,WebFetch" if research else "Read"
        cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--model", model,
               "--system-prompt", prompts.SYSTEM, "--tools", tools, "--allowedTools", tools,
               "--no-session-persistence", "--strict-mcp-config"]
        log("Asking Claude (via Claude Code)...")
        err_file = tempfile.TemporaryFile()
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err_file, cwd=work,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
        timer = threading.Timer(1200, proc.kill)
        timer.start()
        res, fetches, wrote = None, 0, False
        try:
            for raw in proc.stdout:
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                if ev.get("type") == "assistant":
                    for c in ev.get("message", {}).get("content", []):
                        if c.get("type") == "tool_use":
                            fetches += c.get("name") == "WebFetch"
                            log(_describe_tool(c.get("name"), c.get("input") or {}))
                        elif c.get("type") == "text" and "```python" in c.get("text", "") and not wrote:
                            wrote = True
                            log("Writing the build script...")
                elif ev.get("type") == "result":
                    res = ev
            proc.wait()
        finally:
            timer.cancel()
        if res is None:
            err_file.seek(0)
            err = err_file.read().decode("utf-8", "replace").strip()
            if "login" in err.lower() or "auth" in err.lower():
                raise EngineError("Claude Code isn't signed in. Open Settings and click 'Sign in to Claude'.")
            raise EngineError("Claude Code stopped without an answer. " + err[-600:])
        usage.add_claude_code(res, fetches)
        if res.get("is_error"):
            msg = str(res.get("result") or res.get("error") or res)
            if "does not support this model" in msg or "claude update" in msg:
                raise EngineError("Your Claude Code is too old for this model. Update the Claude desktop app "
                                  "(or run 'claude update'), or pick a different model.")
            if "login" in msg.lower() or "/login" in msg:
                raise EngineError("Claude Code isn't signed in. Open Settings and click 'Sign in to Claude'.")
            if "limit" in msg.lower():
                raise EngineError("You've hit your Claude usage limit for now: " + msg[:300])
            raise EngineError("Claude returned an error: " + msg[:800])
        return res.get("result", "")
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------ Anthropic API
def _client(settings):
    import anthropic
    key = settings.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


def _api_tools(model):
    if model == "claude-haiku-5-5":
        return [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5},
                {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 5}]
    return [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5}]


def _ask_api(messages, model, settings, usage, research=False, log=print):
    import anthropic
    client = _client(settings)
    kw = dict(model=model, max_tokens=64000, system=prompts.SYSTEM, messages=messages,
              thinking={"type": "adaptive"}, output_config={"effort": "high"})
    if research:
        kw["tools"] = _api_tools(model)
    if model in ("claude-opus-5-5", "claude-sonnet-5-5"):
        kw.update(betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"})
    log(f"Asking Claude ({model}) via the API...")
    convo = list(messages)
    try:
        for _ in range(6):                           # server tools can pause a long turn; resume it
            t0 = time.time()
            kw["messages"] = convo
            with client.beta.messages.stream(**kw) as stream:
                n, pending = 0, {}
                for ev in stream:
                    et = getattr(ev, "type", "")
                    if et == "content_block_start" and getattr(ev.content_block, "type", "") == "server_tool_use":
                        pending[ev.index] = [ev.content_block.name, ""]
                    elif et == "content_block_delta":
                        dt = getattr(ev.delta, "type", "")
                        if dt == "input_json_delta" and ev.index in pending:
                            pending[ev.index][1] += ev.delta.partial_json
                        elif dt == "text_delta":
                            n += len(ev.delta.text)
                            if n // 3000 != (n - len(ev.delta.text)) // 3000:
                                log(f"Writing the build script... ({n // 1000}k characters)")
                    elif et == "content_block_stop" and ev.index in pending:
                        name, js = pending.pop(ev.index)
                        try:
                            log(_describe_tool(name, json.loads(js or "{}")))
                        except ValueError:
                            log(_describe_tool(name, {}))
                msg = stream.get_final_message()
            usage.add_api(msg.usage, model, time.time() - t0)
            if msg.stop_reason != "pause_turn":
                break
            convo = convo + [{"role": "assistant", "content": msg.content}]
    except anthropic.AuthenticationError:
        raise EngineError("The API key was rejected. Check it in Settings.")
    except anthropic.RateLimitError:
        raise EngineError("Rate limited by the API - wait a minute and try again.")
    except anthropic.APIConnectionError:
        raise EngineError("Couldn't reach the Anthropic API - check your internet connection.")
    except anthropic.APIStatusError as e:
        raise EngineError(f"API error {e.status_code}: {e.message}")
    except TypeError as e:
        if "credentials" in str(e).lower() or "api_key" in str(e).lower():
            raise EngineError("No API key set. Add one in Settings, or switch to the Claude Code engine.")
        raise
    if msg.stop_reason == "refusal":
        raise EngineError("Claude declined this request.")
    text = "".join(b.text for b in msg.content if b.type == "text")
    return text, msg.content


# ------------------------------------------------------------------ parse + run
def extract(text):
    m = re.findall(r"```(?:python|py)\s*\n(.*?)```", text, re.S) or \
        [c for c in re.findall(r"```\s*\n(.*?)```", text, re.S) if "block(" in c or "fill(" in c]
    if not m:
        if "block(" in text or "fill(" in text:
            return None, text, []
        raise EngineError("Claude didn't return a build script. Try rephrasing the prompt.")
    code = max(m, key=len)
    before = text[:text.find("```")].strip().splitlines()
    title = next((ln.strip("#*: ").strip() for ln in before if ln.strip()), None)
    refs = []
    for blk in re.findall(r"```json\s*\n(.*?)```", text, re.S):
        try:
            data = json.loads(blk)
        except ValueError:
            continue
        if isinstance(data, dict):
            data = data.get("references") or [data]
        for r in data if isinstance(data, list) else []:
            if isinstance(r, dict) and str(r.get("url", "")).startswith("http"):
                refs.append({k: str(r.get(k, ""))[:300] for k in ("title", "url", "site", "size", "takeaways")})
    return title, code, refs[:10]


def generate(prompt, size="medium", palette="auto", model=None, engine=None, image=None, parent_id=None,
             research=None, log=print):
    """image: (bytes, mime). Returns the saved build's meta."""
    settings = store.load_settings()
    engine = engine or settings.get("engine", "claude_code")
    model = model or settings.get("model", "claude-opus-5-5")
    prev_code = store.get_code(parent_id) if parent_id else None
    if parent_id and not prev_code:
        raise EngineError("That build has no script, so it can't be edited with a prompt (it was imported).")
    if research is None:
        research = settings.get("research", True) and not parent_id
    sites = [s for s in settings.get("research_sites") or prompts.DEFAULT_SITES if s.strip()]
    palette_text = None
    if str(palette).startswith("custom:"):
        name = palette.split(":", 1)[1]
        palette_text = next((p["description"] for p in settings.get("custom_palettes", []) if p.get("name") == name), None)
    text = prompts.user_message(prompt, size, palette, prev_code, has_image=bool(image),
                                research_sites=sites if research else None, palette_text=palette_text)
    usage = Usage(engine, model)
    started = time.time()
    status, title, saved = "error", None, None
    if research:
        log(f"Researching {len(sites)} schematic sites for reference builds...")

    image_path = None
    ext = None
    if image:
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}.get(image[1], ".png")
        fd, image_path = tempfile.mkstemp(suffix=ext, prefix="ref_")
        with os.fdopen(fd, "wb") as f:
            f.write(image[0])

    try:
        if engine == "api":
            content = [{"type": "text", "text": text}]
            if image:
                content.insert(0, {"type": "image", "source": {
                    "type": "base64", "media_type": image[1], "data": base64.standard_b64encode(image[0]).decode()}})
            messages = [{"role": "user", "content": content}]
            reply, raw = _ask_api(messages, model, settings, usage, research, log)
        else:
            reply = _ask_claude_code(text, model, usage, image_path, research, log)
        title, code, refs = extract(reply)
        if refs:
            log(f"Used {len(refs)} reference build{'s' if len(refs) != 1 else ''} from the web.")

        for attempt in range(MAX_FIX_ATTEMPTS + 1):
            log("Building the blocks...")
            try:
                blocks, meta = sandbox.run_safe(code)
                break
            except sandbox.ScriptError as e:
                if attempt == MAX_FIX_ATTEMPTS:
                    raise EngineError("The build script kept failing: " + str(e)[:600])
                log(f"Script error, asking Claude to fix it (try {attempt + 1}/{MAX_FIX_ATTEMPTS})...")
                if engine == "api":
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": prompts.fix_message(str(e))})
                    reply, raw = _ask_api(messages, model, settings, usage, False, log)
                else:
                    fix_text = prompts.user_message(prompt, size, palette, prev_code, has_image=bool(image),
                                                    palette_text=palette_text)
                    reply = _ask_claude_code(
                        fix_text + "\n\nYour previous script:\n```python\n" + code + "\n```\n\n" + prompts.fix_message(str(e)),
                        model, usage, image_path, False, log)
                t2, code, refs2 = extract(reply)
                title = title or t2
                refs = refs or refs2

        title = meta.get("name") or title or prompt[:60] or "Build"
        rec = usage.record()
        log(f"Done: {len(blocks):,} blocks. Claude used {rec['total_tokens']:,} tokens "
            f"(about ${rec['cost_usd']:.2f}).")
        img_bytes = image[0] if image else None
        if parent_id and not image:
            pm = store.get_meta(parent_id)
            if pm.get("image"):
                with open(store.file_path(parent_id, pm["image"]), "rb") as f:
                    img_bytes = f.read()
                ext = os.path.splitext(pm["image"])[1]
        saved = store.save_build(blocks, title, prompt=prompt, code=code, source=engine, parent=parent_id,
                                 model=model, description=meta.get("description") or "",
                                 image_bytes=img_bytes, image_ext=ext, usage=rec, references=refs,
                                 researched=bool(research))
        status = "done"
        return saved
    finally:
        rec = usage.record()
        if rec["requests"]:
            store.log_usage({**rec, "status": status, "prompt": prompt[:200], "title": (saved or {}).get("title") or title,
                             "build_id": (saved or {}).get("id"), "parent": parent_id, "researched": bool(research),
                             "time": started, "wall_seconds": round(time.time() - started, 1)})
        if image_path:
            try:
                os.remove(image_path)
            except OSError:
                pass
