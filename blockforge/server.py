"""BlockForge local server: serves the app UI and its JSON API on http://127.0.0.1:8765"""
import base64
import json
import mimetypes
import re
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from blockforge import eleven, engine, exporters, learn, mods, pixelart, placement, prompts, sandbox, store, tts, updater, voices  # noqa: E402
from blockforge.version import VERSION  # noqa: E402

PORT = int(os.environ.get("BLOCKFORGE_PORT", "8765"))
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
JOBS = {}


def start_job(fn, **kw):
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "status": "running", "log": [], "build": None, "error": None, "started": time.time()}
    JOBS[jid] = job

    def log(msg):
        job["log"].append({"t": round(time.time() - job["started"], 1), "msg": msg})

    def run():
        try:
            job["build"] = fn(log=log, **kw)
            job["status"] = "done"
        except (engine.EngineError, sandbox.ScriptError, updater.UpdateError, RuntimeError, ValueError, OSError) as e:
            job["error"] = str(e)
            job["status"] = "error"
        except Exception as e:                       # noqa: BLE001
            traceback.print_exc()
            job["error"] = f"{type(e).__name__}: {e}"
            job["status"] = "error"
    threading.Thread(target=run, daemon=True).start()
    return job


def run_script_job(code, title="Script build", parent_id=None, log=print):
    log("Running your script...")
    pack, version, popts = mods.build_opts()
    blocks, meta = sandbox.run_safe(code, placement_opts=popts)
    final = placement.process(blocks, final=True, **popts)
    sandbox.restore_modules(blocks, meta)
    fixes = (meta.get("fixes") or []) + final["fixed"]
    for f in fixes:
        log("Auto-fixed: " + f)
    prompt = store.get_meta(parent_id).get("prompt", "") if parent_id else ""
    saved = store.save_build(blocks, meta.get("name") or title, prompt=prompt, code=code, source="script",
                             parent=parent_id, description=meta.get("description") or "",
                             warnings=meta.get("redstone_warnings") or [], fixes=fixes,
                             data_version=mods.data_version(version), modpack=(pack or {}).get("name"),
                             tiles=sandbox.tiles_of(meta), modules=meta.get("modules"))
    if parent_id:
        learn.log_correction(parent_id, saved["id"])           # keeps "AI version -> your fix" for learning
        saved = store.get_meta(saved["id"])
    return saved


class H(BaseHTTPRequestHandler):
    server_version = "BlockForge/1.0"

    def log_message(self, fmt, *a):
        pass

    # -------------------------------------------------- helpers
    def send(self, code, body=b"", ctype="application/json", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def json_body(self):
        try:
            return json.loads(self.body() or b"{}")
        except ValueError:
            return {}

    def err(self, code, msg):
        self.send(code, {"error": msg})

    def _local_only(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        origin = self.headers.get("Origin")
        if host not in ("127.0.0.1", "localhost") or (origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost")):
            self.err(403, "forbidden")
            return False
        return True

    # -------------------------------------------------- routes
    def do_GET(self):
        if not self._local_only():
            return
        path = unquote(urlparse(self.path).path)
        parts = [p for p in path.split("/") if p]
        try:
            if not parts or parts[0] != "api":
                return self.static(path)
            if parts[1:] == ["builds"]:
                return self.send(200, store.list_builds())
            if parts[1:] == ["status"]:
                s = store.load_settings()
                key = s.get("api_key") or ""
                return self.send(200, {
                    "settings": {**{k: v for k, v in s.items() if k not in ("providers", "eleven")}, "api_key": ("•" * 8 + key[-4:]) if key else ""},
                    "has_api_key": bool(key or os.environ.get("ANTHROPIC_API_KEY")),
                    "claude_code": engine.claude_status(),
                    "models": engine.MODELS, "formats": {k: v[0] for k, v in exporters.FORMATS.items()},
                    "default_sites": prompts.DEFAULT_SITES, "palettes": list(prompts.PALETTES),
                    "version": VERSION, "pixel_palettes": pixelart.palette_info(), "hd_voice": tts.available(), "hd_voices": voices.installed(),
                    "voice_catalog": voices.catalog_info(), "eleven_models": eleven.MODELS,
                    "eleven": {"key_set": bool((s.get("eleven") or {}).get("api_key")),
                               "voice_id": (s.get("eleven") or {}).get("voice_id", ""),
                               "voice_name": (s.get("eleven") or {}).get("voice_name", ""),
                               "model": (s.get("eleven") or {}).get("model") or "eleven_flash_v2_5"},
                    "providers": {pid: {**meta, "key_set": bool(((s.get("providers") or {}).get(pid) or {}).get("api_key")),
                                        **{k: v for k, v in ((s.get("providers") or {}).get(pid) or {}).items() if k != "api_key"}}
                                  for pid, meta in engine.PROVIDERS.items()},
                    "engine_label": engine.engine_label(s.get("engine", "claude_code")),
                })
            if parts[1:] == ["tts"]:
                q = parse_qs(urlparse(self.path).query)
                try:
                    wav = tts.speak(q.get("text", [""])[0], q.get("voice", ["joe"])[0], q.get("speed", ["1"])[0])
                except FileNotFoundError as e:
                    return self.err(404, str(e))
                except (ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
                    return self.err(400, str(e))
                return self.send(200, wav, "audio/wav")
            if parts[1:] == ["eleven", "voices"]:
                try:
                    return self.send(200, {"voices": eleven.list_voices(), "usage": eleven.usage()})
                except eleven.ElevenError as e:
                    return self.err(400, str(e))
            if parts[1:] == ["eleven", "usage"]:
                try:
                    return self.send(200, {"usage": eleven.usage()})
                except eleven.ElevenError as e:
                    return self.err(400, str(e))
            if parts[1:] == ["eleven", "tts"]:
                q = parse_qs(urlparse(self.path).query)
                try:
                    mp3 = eleven.speak(q.get("text", [""])[0], q.get("voice", [None])[0], q.get("model", [None])[0],
                                       q.get("speed", ["1"])[0])
                except eleven.ElevenError as e:
                    return self.err(400, str(e))
                return self.send(200, mp3, "audio/mpeg")
            if parts[1:] == ["models"]:
                pid = parse_qs(urlparse(self.path).query).get("provider", [""])[0]
                try:
                    models = engine.list_models(pid)
                except engine.EngineError as e:
                    return self.err(400, str(e))
                provs = store.load_settings().get("providers") or {}
                provs.setdefault(pid, {})["models"] = models[:400]
                store.save_settings({"providers": provs})
                return self.send(200, {"models": models})
            if parts[1:] == ["update"]:
                force = "force" in parse_qs(urlparse(self.path).query)
                try:
                    return self.send(200, updater.check(force))
                except updater.UpdateError as e:
                    return self.err(502, str(e))
            if parts[1:] == ["usage"]:
                return self.send(200, store.usage_summary())
            if parts[1:] == ["learning"]:
                s = store.load_settings()
                return self.send(200, {**learn.stats(), "examples": s.get("learn_examples", True), "log": s.get("learn_log", True),
                                       "tags": learn.RATING_TAGS})
            if parts[1] == "mods":
                s = store.load_settings()
                if parts[2:] == []:
                    return self.send(200, {"packs": mods.list_packs(), "active": s.get("active_pack"),
                                           "use_mods": s.get("use_mods", True), "target_version": s.get("target_version"),
                                           "versions": mods.installed_versions()})
                if parts[2:] == ["detect"]:
                    known = {os.path.normcase(p.get("path", "")) for p in s.get("modpacks", [])}
                    found = []
                    for d in mods.detect_instances():
                        mdir = d.get("mods_dir") or d.get("path") or ""
                        found.append({**d, "added": os.path.normcase(mdir) in known})
                    return self.send(200, {"instances": found})
                if len(parts) == 4 and parts[2] == "pack":
                    idx = mods.load_index(parts[3])
                    if not idx:
                        return self.err(404, "no such pack")
                    return self.send(200, {**mods.summary(idx), "list": [
                        {"file": m["file"], "id": m["id"], "name": m["name"], "version": m.get("version"),
                         "blocks": len(m["blocks"]), "enabled": m.get("enabled", True)} for m in idx["mods"]]})
                if parts[2:] == ["search"]:
                    q = parse_qs(urlparse(self.path).query)
                    idx = mods.load_index(q.get("pack", [s.get("active_pack") or ""])[0])
                    return self.send(200, {"blocks": mods.search(idx, q.get("q", [""])[0]) if idx else []})
            if parts[1] == "jobs" and len(parts) == 3:
                job = JOBS.get(parts[2])
                return self.send(200, job) if job else self.err(404, "no such job")
            if parts[1] == "builds" and len(parts) >= 3:
                bid = parts[2]
                if len(parts) == 3:
                    return self.send(200, store.get_meta(bid))
                if parts[3] == "blocks":
                    return self.send(200, store.get_blocks_raw(bid))
                if parts[3] == "code":
                    return self.send(200, {"code": store.get_code(bid)})
                if parts[3] == "file" and len(parts) == 5:
                    p = store.file_path(bid, parts[4])
                    with open(p, "rb") as f:
                        return self.send(200, f.read(), mimetypes.guess_type(p)[0] or "application/octet-stream")
                if parts[3] == "export" and len(parts) == 5:
                    fmt = parts[4]
                    if fmt not in exporters.FORMATS:
                        return self.err(400, "unknown format")
                    p = store.export_path(bid, fmt)
                    with open(p, "rb") as f:
                        return self.send(200, f.read(), "application/octet-stream",
                                         {"Content-Disposition": f'attachment; filename="{os.path.basename(p)}"'})
            self.err(404, "not found")
        except KeyError:
            self.err(404, "not found")
        except Exception as e:                       # noqa: BLE001
            traceback.print_exc()
            self.err(500, str(e))

    def do_POST(self):
        if not self._local_only():
            return
        parts = [p for p in unquote(urlparse(self.path).path).split("/") if p]
        try:
            if parts[:1] != ["api"]:
                return self.err(404, "not found")
            route = parts[1:]
            if route == ["generate"]:
                b = self.json_body()
                image = None
                if b.get("image"):
                    head, data = b["image"].split(",", 1)
                    image = (base64.b64decode(data), head.split(";")[0].split(":")[1])
                if not (b.get("prompt") or "").strip() and not image:
                    return self.err(400, "Describe a build or attach an image.")
                job = start_job(engine.generate, prompt=b.get("prompt", ""), size=b.get("size", "medium"),
                                palette=b.get("palette", "auto"), model=b.get("model"), engine=b.get("engine"),
                                image=image, parent_id=b.get("parent_id"), research=b.get("research"),
                                redstone=b.get("redstone"), use_mods=b.get("use_mods"))
                return self.send(200, {"job": job["id"]})
            if route == ["run"]:
                b = self.json_body()
                job = start_job(run_script_job, code=b.get("code", ""), title=b.get("title") or "Script build",
                                parent_id=b.get("parent_id"))
                return self.send(200, {"job": job["id"]})
            if route == ["import"]:
                name = unquote(self.headers.get("X-Filename") or "import.schem")
                blocks = exporters.import_file(self.body())
                if not blocks:
                    return self.err(400, "That file has no blocks in it.")
                meta = store.save_build(blocks, os.path.splitext(name)[0], source="import")
                return self.send(200, meta)
            if route == ["settings"]:
                b = self.json_body()
                if "api_key" in b and b["api_key"].startswith("•"):
                    b.pop("api_key")
                b.pop("modpacks", None)                      # only the Mods endpoints manage packs
                if "research_sites" in b:
                    sites = [re.sub(r"^https?://(www\.)?", "", str(s).strip()).strip("/") for s in b["research_sites"] or []]
                    b["research_sites"] = [s for s in sites if s][:20] or None
                if "custom_palettes" in b:
                    b["custom_palettes"] = [{"name": str(p.get("name", ""))[:40], "description": str(p.get("description", ""))[:400]}
                                            for p in b["custom_palettes"] or [] if str(p.get("name", "")).strip()][:30]
                if "eleven" in b and isinstance(b["eleven"], dict):
                    cur = store.load_settings().get("eleven") or {}
                    new = {**cur, **{k: str(b["eleven"][k]).strip() for k in ("voice_id", "voice_name", "model")
                                     if k in b["eleven"]}}
                    k = b["eleven"].get("api_key")
                    if k is not None and not str(k).startswith("•"):
                        new["api_key"] = str(k).strip()
                    b["eleven"] = new
                elif "eleven" in b:
                    b.pop("eleven")
                if "providers" in b:
                    cur = store.load_settings().get("providers") or {}
                    for pid, cfg in (b["providers"] or {}).items():
                        if pid not in engine.PROVIDERS or not isinstance(cfg, dict):
                            continue
                        old = cur.get(pid, {})
                        new = {**old, **{k: str(cfg[k]).strip() for k in ("base_url", "model") if k in cfg}}
                        k = cfg.get("api_key")
                        if k is not None and not str(k).startswith("•"):
                            new["api_key"] = str(k).strip()
                        cur[pid] = new
                    b["providers"] = cur
                for k in ("ui", "guide"):
                    if k in b and not isinstance(b[k], dict):
                        b.pop(k)
                return self.send(200, {"ok": True, "engine": store.save_settings(b)["engine"]})
            if route == ["pixelart"]:
                b = self.json_body()
                try:
                    w, h = int(b.get("w", 0)), int(b.get("h", 0))
                    rgba = base64.b64decode(b.get("rgba", ""))
                except (TypeError, ValueError):
                    return self.err(400, "bad picture data")
                blocks = pixelart.convert(w, h, rgba, b.get("palette", "concrete"), bool(b.get("dither", False)),
                                          "floor" if b.get("orient") == "floor" else "wall", int(b.get("max_colors") or 0), int(b.get("scale") or 1))
                title = (str(b.get("title") or "Pixel art").strip() or "Pixel art")[:60]
                meta = store.save_build(blocks, title, prompt="Pixel art from a picture (" + str(b.get("palette", "concrete")) + ")",
                                        source="pixelart")
                return self.send(200, meta)
            if route == ["learning", "clear"]:
                learn.clear()
                return self.send(200, {"ok": True})
            if route[:1] == ["mods"] and len(route) == 2:
                b = self.json_body()
                act = route[1]
                if act == "add":
                    d = mods.resolve_mods_dir(b.get("path", ""))
                    name = (b.get("name") or "").strip() or None

                    def do_scan(log=print):
                        idx = mods.scan(d, name, log)
                        mods.register_pack(idx)
                        return mods.summary(idx)
                    return self.send(200, {"job": start_job(do_scan)["id"]})
                if act == "rescan":
                    idx = mods.load_index(b.get("pack", ""))
                    if not idx:
                        return self.err(404, "no such pack")

                    def do_rescan(log=print):
                        new = mods.scan(idx["path"], idx["name"], log)
                        mods.register_pack(new)
                        return mods.summary(new)
                    return self.send(200, {"job": start_job(do_rescan)["id"]})
                if act == "toggle":
                    idx = mods.load_index(b.get("pack", ""))
                    if not idx:
                        return self.err(404, "no such pack")
                    files = b.get("files") or [b.get("file")]
                    for m in idx["mods"]:
                        if m["file"] in files:
                            m["enabled"] = bool(b.get("enabled"))
                    with open(mods.pack_file(idx["id"]), "w", encoding="utf-8") as f:
                        json.dump(idx, f, separators=(",", ":"))
                    return self.send(200, mods.summary(idx))
                if act == "remove":
                    mods.forget_pack(b.get("pack", ""))
                    return self.send(200, {"ok": True})
                if act == "colors":
                    names = [str(n) for n in (b.get("names") or [])][:3000]
                    colors = mods.mod_colors([n for n in names if ":" in n and not n.startswith("minecraft:")])
                    vanilla = {n.replace("minecraft:", "") for n in names if ":" not in n or n.startswith("minecraft:")}
                    if vanilla:                                  # real texture colours, so pixel art previews true to the game
                        from blockforge import texpalette
                        v = texpalette.best_version()
                        data = texpalette.load(v) if v else None
                        for n, rgb, _ in (data or {}).get("wall", []):
                            k = n.replace("minecraft:", "")
                            if k in vanilla:
                                colors[k] = "#%02x%02x%02x" % tuple(rgb)
                    return self.send(200, {"colors": colors})
                return self.err(404, "not found")
            if route == ["voices", "download"]:
                vid = self.json_body().get("id", "")
                if vid not in voices.CATALOG:
                    return self.err(400, "Unknown voice")
                job = start_job(lambda log=print: {"id": vid, "done": voices.download(vid, log)})
                return self.send(200, {"job": job["id"]})
            if route == ["update"]:
                def do_update(log=print):
                    res = updater.install(log)
                    threading.Timer(2.5, os._exit, [0]).start()     # close so the installer can replace our files
                    return res
                job = start_job(do_update)
                return self.send(200, {"job": job["id"]})
            if route == ["login"]:
                engine.open_claude_login()
                return self.send(200, {"ok": True})
            if len(route) == 3 and route[0] == "builds":
                bid, action = route[1], route[2]
                if action == "rename":
                    t = (self.json_body().get("title") or "").strip()[:80]
                    return self.send(200, store.update_meta(bid, title=t or "Untitled build"))
                if action == "rate":
                    b = self.json_body()
                    return self.send(200, learn.rate(bid, b.get("rating"), b.get("tags"), b.get("note", "")))
                if action == "thumb":
                    data = self.json_body().get("image", "")
                    if not data.startswith("data:image/jpeg;base64,"):
                        return self.err(400, "bad image")
                    with open(os.path.join(store._dir(bid), "thumb.jpg"), "wb") as f:
                        f.write(base64.b64decode(data.split(",", 1)[1]))
                    m = store.update_meta(bid, has_thumb=True, thumb_v=int(time.time()))
                    return self.send(200, {"ok": True, "thumb_v": m["thumb_v"]})
                if action == "reveal":
                    fmt = self.json_body().get("format", "schem")
                    p = store.export_path(bid, fmt)
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
                    return self.send(200, {"ok": True, "path": p})
            self.err(404, "not found")
        except KeyError:
            self.err(404, "not found")
        except (ValueError, engine.EngineError) as e:
            self.err(400, str(e))
        except Exception as e:                       # noqa: BLE001
            traceback.print_exc()
            self.err(500, str(e))

    def do_DELETE(self):
        if not self._local_only():
            return
        parts = [p for p in unquote(urlparse(self.path).path).split("/") if p]
        if len(parts) == 3 and parts[:2] == ["api", "builds"]:
            try:
                store.delete_build(parts[2])
                return self.send(200, {"ok": True})
            except (KeyError, OSError):
                return self.err(404, "not found")
        self.err(404, "not found")

    def static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        p = os.path.normpath(os.path.join(STATIC, rel))
        if not p.startswith(STATIC) or not os.path.isfile(p):
            return self.err(404, "not found")
        with open(p, "rb") as f:
            ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
            if p.endswith(".js"):
                ctype = "text/javascript"
            self.send(200, f.read(), ctype)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"BlockForge running at http://127.0.0.1:{PORT}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
