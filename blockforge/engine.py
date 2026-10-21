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

    def add_openai(self, u, seconds, local=False):
        d = self.d
        d["requests"] += 1
        d["turns"] += 1
        d["seconds"] += seconds
        cached = ((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        d["input_tokens"] += max(0, (u.get("prompt_tokens") or 0) - cached)
        d["cache_read_tokens"] += cached
        d["output_tokens"] += u.get("completion_tokens") or 0
        d["thinking_tokens"] += ((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
        if u.get("cost"):                            # OpenRouter reports the real cost
            d["cost_usd"] += float(u["cost"])
        self.local = local

    def record(self):
        r = dict(self.d)
        r["cost_usd"] = round(r["cost_usd"], 4)
        r["seconds"] = round(r["seconds"], 1)
        r["total_tokens"] = r["input_tokens"] + r["output_tokens"] + r["cache_read_tokens"] + r["cache_write_tokens"]
        if r["engine"] == "claude_code":
            r["billing"] = "Included in your Claude plan (cost shown at API list price)"
        elif r["engine"] == "api":
            r["billing"] = "Charged to your Anthropic API key"
        elif getattr(self, "local", False):
            r["billing"] = "Free: ran on your own PC"
        elif r["cost_usd"]:
            r["billing"] = f"Charged by {engine_label(r['engine'])}"
        else:
            r["billing"] = f"Charged by {engine_label(r['engine'])} (it doesn't report the cost, so check your account)"
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
def _ask_claude_code(text, model, usage, image_path=None, research=False, log=print, pack=None):
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
        if pack:
            from . import mods
            mods.write_id_file(pack, work)
            tools += ",Grep"
            text += ("\n\nEvery modded block id in the player's pack is listed in modded_blocks.txt in the current folder "
                     "(one per line: id<TAB>mod name). Use Grep on it to find the exact id before using any modded block.")
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


# ------------------------------------------------------------------ other AIs (OpenAI-style chat APIs)
PROVIDERS = {
    "openai": {"name": "OpenAI (ChatGPT)", "base": "https://api.openai.com/v1", "key": True,
               "key_url": "https://platform.openai.com/api-keys"},
    "gemini": {"name": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "key": True,
               "key_url": "https://aistudio.google.com/apikey"},
    "openrouter": {"name": "OpenRouter (hundreds of models)", "base": "https://openrouter.ai/api/v1", "key": True,
                   "key_url": "https://openrouter.ai/keys"},
    "deepseek": {"name": "DeepSeek", "base": "https://api.deepseek.com/v1", "key": True,
                 "key_url": "https://platform.deepseek.com/api_keys"},
    "xai": {"name": "xAI Grok", "base": "https://api.x.ai/v1", "key": True, "key_url": "https://console.x.ai/"},
    "mistral": {"name": "Mistral", "base": "https://api.mistral.ai/v1", "key": True,
                "key_url": "https://console.mistral.ai/api-keys"},
    "groq": {"name": "Groq", "base": "https://api.groq.com/openai/v1", "key": True,
             "key_url": "https://console.groq.com/keys"},
    "lmstudio": {"name": "LM Studio (on this PC, free)", "base": "http://localhost:1234/v1", "key": False, "local": True},
    "ollama": {"name": "Ollama (on this PC, free)", "base": "http://localhost:11434/v1", "key": False, "local": True},
    "custom": {"name": "Custom (any OpenAI-compatible API)", "base": "", "key": None},
}
CLAUDE_ENGINES = ("claude_code", "api")


def engine_label(engine):
    if engine == "claude_code":
        return "Claude (your account)"
    if engine == "api":
        return "Claude (API key)"
    return PROVIDERS.get(engine, {}).get("name", engine).split(" (")[0]


def _provider_cfg(pid, settings):
    meta = PROVIDERS.get(pid)
    if not meta:
        raise EngineError(f"Unknown AI provider '{pid}'.")
    cfg = (settings.get("providers") or {}).get(pid, {})
    base = (cfg.get("base_url") or meta["base"]).rstrip("/")
    if not base:
        raise EngineError(f"Set the API address for {meta['name']} in Settings → AI.")
    key = cfg.get("api_key") or ""
    if meta["key"] and not key:
        raise EngineError(f"Add your {meta['name'].split(' (')[0]} API key in Settings → AI.")
    return meta, base, key, cfg


def _http_json(url, key=None, body=None, timeout=900):
    import urllib.error
    import urllib.request
    headers = {"Content-Type": "application/json", "User-Agent": "BlockForge"}
    if key:
        headers["Authorization"] = "Bearer " + key
    if "openrouter.ai" in url:
        headers.update({"HTTP-Referer": "https://github.com/Ryn-labs/BlockForge", "X-Title": "BlockForge"})
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")[:600]
        try:
            msg = json.loads(text).get("error", text)
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except ValueError:
            msg = text
        raise _HTTPError(e.code, str(msg))
    except urllib.error.URLError as e:
        raise _HTTPError(0, str(e.reason))


class _HTTPError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code, self.msg = code, msg


def list_models(pid):
    settings = store.load_settings()
    meta, base, key, _ = _provider_cfg(pid, settings)
    try:
        data = _http_json(base + "/models", key, timeout=20)
    except _HTTPError as e:
        raise EngineError(_friendly(meta, e))
    items = data.get("data") if isinstance(data, dict) else data
    ids = sorted({(m.get("id") or m.get("name") or "").replace("models/", "") for m in items or [] if isinstance(m, dict)})
    return [i for i in ids if i and not re.search(r"embed|whisper|tts|dall-e|moderation|image|audio|rerank|transcri", i, re.I)]


def _friendly(meta, e):
    name = meta["name"].split(" (")[0]
    if e.code == 0:
        if meta.get("local"):
            return (f"Couldn't reach {name}. Open {name}, load a model and start its local server "
                    f"(LM Studio: Developer tab → Start server). Details: {e.msg}")
        return f"Couldn't reach {name}: {e.msg}"
    if e.code in (401, 403):
        return f"{name} rejected the API key ({e.code}). Check it in Settings → AI."
    if e.code == 404:
        return f"{name} doesn't have that model ({e.msg[:200]}). Pick another in the Model menu."
    if e.code == 402:
        return f"Your {name} account is out of credit."
    if e.code == 429:
        return f"{name} is rate limiting you or you're out of quota: {e.msg[:200]}"
    return f"{name} error {e.code}: {e.msg[:300]}"


def _ask_openai_compat(pid, messages, model, settings, usage, log=print):
    meta, base, key, cfg = _provider_cfg(pid, settings)
    model = model or cfg.get("model")
    if not model:
        raise EngineError(f"Pick a {meta['name'].split(' (')[0]} model in the Model menu (Settings → AI → Load models).")
    log(f"Asking {meta['name'].split(' (')[0]} ({model})...")
    body = {"model": model, "messages": messages}
    if not meta.get("local"):
        body["max_completion_tokens" if pid == "openai" else "max_tokens"] = 32000
    t0 = time.time()
    try:
        try:
            res = _http_json(base + "/chat/completions", key, body)
        except _HTTPError as e:                      # some models cap output lower: retry with their default
            if e.code == 400 and re.search(r"max_(completion_)?tokens", e.msg):
                body.pop("max_tokens", None)
                body.pop("max_completion_tokens", None)
                res = _http_json(base + "/chat/completions", key, body)
            else:
                raise
    except _HTTPError as e:
        raise EngineError(_friendly(meta, e))
    choice = (res.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    if isinstance(text, list):                       # some APIs return content parts
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    usage.add_openai(res.get("usage") or {}, time.time() - t0, local=bool(meta.get("local")))
    if not text.strip():
        raise EngineError(f"{meta['name'].split(' (')[0]} returned an empty answer "
                          f"({choice.get('finish_reason') or 'no reason given'}). Try another model.")
    if choice.get("finish_reason") == "length" and "```" in text and text.count("```") % 2:
        log("The answer was cut off at the model's length limit; asking it to finish...")
    return text


# ------------------------------------------------------------------ the generation loop (every AI)
class _Conversation:
    """Hides the differences between AIs: first ask, then follow-up fix requests."""

    def __init__(self, engine, model, settings, usage, text, image, image_path, research, log, pack=None):
        self.pack = pack
        self.e, self.model, self.settings, self.usage, self.log = engine, model, settings, usage, log
        self.text, self.image, self.image_path, self.research = text, image, image_path, research
        self.messages, self.raw, self.last_code = None, None, None

    def first(self):
        if self.e == "api":
            content = [{"type": "text", "text": self.text}]
            if self.image:
                content.insert(0, {"type": "image", "source": {
                    "type": "base64", "media_type": self.image[1],
                    "data": base64.standard_b64encode(self.image[0]).decode()}})
            self.messages = [{"role": "user", "content": content}]
            reply, self.raw = _ask_api(self.messages, self.model, self.settings, self.usage, self.research, self.log)
            return reply
        if self.e == "claude_code":
            return _ask_claude_code(self.text, self.model, self.usage, self.image_path, self.research, self.log, self.pack)
        user = self.text
        if self.image:
            user = [{"type": "text", "text": self.text}, {"type": "image_url", "image_url": {
                "url": f"data:{self.image[1]};base64," + base64.standard_b64encode(self.image[0]).decode()}}]
        self.messages = [{"role": "system", "content": prompts.SYSTEM}, {"role": "user", "content": user}]
        reply = _ask_openai_compat(self.e, self.messages, self.model, self.settings, self.usage, self.log)
        self.raw = reply
        return reply

    def follow_up(self, message, code):
        if self.e == "api":
            self.messages += [{"role": "assistant", "content": self.raw}, {"role": "user", "content": message}]
            reply, self.raw = _ask_api(self.messages, self.model, self.settings, self.usage, False, self.log)
            return reply
        if self.e == "claude_code":
            return _ask_claude_code(self.text_without_research() + "\n\nYour previous script:\n```python\n" + code
                                    + "\n```\n\n" + message, self.model, self.usage, self.image_path, False, self.log, self.pack)
        self.messages += [{"role": "assistant", "content": self.raw}, {"role": "user", "content": message}]
        self.raw = _ask_openai_compat(self.e, self.messages, self.model, self.settings, self.usage, self.log)
        return self.raw

    def text_without_research(self):
        return self.text.split("## Research first (required)")[0]


def generate(prompt, size="medium", palette="auto", model=None, engine=None, image=None, parent_id=None,
             research=None, redstone=None, use_mods=None, log=print):
    """image: (bytes, mime). Returns the saved build's meta."""
    settings = store.load_settings()
    engine = engine or settings.get("engine", "claude_code")
    if engine not in CLAUDE_ENGINES and engine not in PROVIDERS:
        engine = "claude_code"
    if engine in CLAUDE_ENGINES:
        model = model if model in MODELS else settings.get("model", "claude-opus-5-5")
    else:
        model = model or ((settings.get("providers") or {}).get(engine, {}).get("model"))
    who = engine_label(engine)
    prev_code = store.get_code(parent_id) if parent_id else None
    if parent_id and not prev_code:
        raise EngineError("That build has no script, so it can't be edited with a prompt (it was imported).")
    if research is None:
        research = settings.get("research", True) and not parent_id
    if research and engine not in CLAUDE_ENGINES:
        log(f"Online research needs Claude, so {who} will design this one without it.")
        research = False
    if redstone is None:
        redstone = prompts.wants_redstone(prompt, prev_code)
    sites = [s for s in settings.get("research_sites") or prompts.DEFAULT_SITES if s.strip()]
    palette_text = None
    if str(palette).startswith("custom:"):
        pname = palette.split(":", 1)[1]
        palette_text = next((p["description"] for p in settings.get("custom_palettes", []) if p.get("name") == pname), None)
    from . import learn, mods, placement
    if use_mods is None:
        use_mods = settings.get("use_mods", True)
    pack = mods.load_index(settings["active_pack"]) if use_mods and settings.get("active_pack") else None
    version = (pack or {}).get("mc") or settings.get("target_version") or "1.21.1"
    popts = {"pack": pack, "version": version}
    mods_text = mods.prompt_section(pack, prompt) if pack else None
    if pack:
        log(f"Using blocks from your modpack: {pack['name']} ({sum(len(m['blocks']) for m in pack['mods'] if m.get('enabled', True)):,} blocks).")
    text = prompts.user_message(prompt, size, palette, prev_code, has_image=bool(image),
                                research_sites=sites if research else None, palette_text=palette_text,
                                redstone=redstone, version=version, mods_text=mods_text,
                                learned_text=learn.prompt_section(prompt))
    usage = Usage(engine, model)
    started = time.time()
    status, title, saved = "error", None, None
    if redstone:
        log("This looks like a redstone build: using the redstone guide and checker.")
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
        convo = _Conversation(engine, model, settings, usage, text, image, image_path, research, log, pack)
        title, code, refs = extract(convo.first())
        if refs:
            log(f"Used {len(refs)} reference build{'s' if len(refs) != 1 else ''} from the web.")

        def build(code):
            nonlocal title, refs
            for attempt in range(MAX_FIX_ATTEMPTS + 1):
                log("Building the blocks...")
                try:
                    return code, *sandbox.run_safe(code, placement_opts=popts)
                except sandbox.ScriptError as e:
                    if attempt == MAX_FIX_ATTEMPTS:
                        raise EngineError("The build script kept failing: " + str(e)[:600])
                    log(f"Script error, asking {who} to fix it (try {attempt + 1}/{MAX_FIX_ATTEMPTS})...")
                    t2, code, refs2 = extract(convo.follow_up(prompts.fix_message(str(e)), code))
                    title = title or t2
                    refs = refs or refs2

        code, blocks, meta = build(code)
        problems = meta.get("warnings") or []
        for f in meta.get("fixes") or []:
            log("Auto-fixed: " + f)
        if problems:
            log("Build check: " + "; ".join(problems)[:300])
            log(f"Asking {who} to fix {'the redstone and ' if redstone else ''}blocks that can't exist...")
            try:
                _, code2, _ = extract(convo.follow_up(prompts.redstone_fix_message(problems), code))
                code2, blocks2, meta2 = build(code2)
                if len(meta2.get("warnings") or []) <= len(problems):
                    code, blocks, meta = code2, blocks2, meta2
                    problems = meta.get("warnings") or []
            except EngineError as e:
                log(f"Kept the first version ({e}).")
        final = placement.process(blocks, final=True, **popts)          # last resort: nothing impossible is left
        sandbox.restore_modules(blocks, meta)
        fixes = list(meta.get("fixes") or []) + final["fixed"]
        for f in final["fixed"]:
            log("Auto-fixed: " + f)
        problems = list(meta.get("redstone_warnings") or [])
        log("Build check passed: every block can exist where it is." if not problems else "Redstone notes: " + "; ".join(problems)[:300])

        title = meta.get("name") or title or prompt[:60] or "Build"
        rec = usage.record()
        cost = f" (about ${rec['cost_usd']:.2f})" if rec["cost_usd"] else ""
        log(f"Done: {len(blocks):,} blocks. {who} used {rec['total_tokens']:,} tokens{cost}.")
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
                                 researched=bool(research), redstone=bool(redstone), warnings=problems, fixes=fixes,
                                 data_version=mods.data_version(version), modpack=(pack or {}).get("name"),
                                 tiles=sandbox.tiles_of(meta), modules=meta.get("modules"))
        status = "done"
        learn.log_generation(saved, fixes, list(meta.get("redstone_warnings") or []))
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
