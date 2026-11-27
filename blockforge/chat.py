"""Talk to BlockForge: one chat per build draft.

A chat lives in DATA/chats/<id>.json (messages, the plan, versions) and owns one build session (blockforge/session.py).
Every AI turn that changes blocks becomes a version; a version keeps a copy of the session file in DATA/chats/<id>/, so
undo, "go back to this version" (a new branch, nothing is deleted) and compare never depend on the session's own undo."""
import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid

from . import checks, exporters, loop, selfimprove, session, share, store

DIR = os.path.join(store.DATA, "chats")
SCOPE_PAD = 2                   # a scoped change may grow this many blocks past the part's box (a steeper roof needs room)
HISTORY_MESSAGES = 14
MAX_QUESTIONS = 3
_LOCKS = {}
_BUSY = set()
_PROCS = {}                      # chat id -> the running AI process (for Pause)
_PAUSED = set()
_GUARD = threading.Lock()


class ChatError(ValueError):
    pass


def _path(cid):
    if not re.fullmatch(r"[0-9a-f]{6,32}", str(cid or "")):
        raise KeyError(cid)
    return os.path.join(DIR, cid + ".json")


def _snap_dir(cid):
    return os.path.join(DIR, cid)


def _lock(cid):
    with _GUARD:
        return _LOCKS.setdefault(cid, threading.RLock())


def load(cid):
    try:
        with open(_path(cid), encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        raise KeyError(cid) from None


def save_state(c):
    os.makedirs(DIR, exist_ok=True)
    tmp = _path(c["id"]) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, separators=(",", ":"))
    os.replace(tmp, _path(c["id"]))


def list_chats():
    out = []
    try:
        names = os.listdir(DIR)
    except OSError:
        return out
    for n in names:
        if n.endswith(".json"):
            try:
                c = load(n[:-5])
            except (KeyError, ValueError):
                continue
            out.append({"id": c["id"], "title": c.get("title"), "created": c.get("created"), "updated": c.get("updated")})
    return sorted(out, key=lambda c: -(c.get("updated") or 0))


# ------------------------------------------------------------------ session files and diffs
def _sfile(sid):
    return os.path.join(session.DIR, sid + ".json")


def _blocks_of(sid):
    return session.load(sid).blocks


def _copy_session(src, dst_sid, new_id):
    """Write the session file `src` as session `dst_sid` (the id inside the file is changed)."""
    with open(src, encoding="utf-8") as f:
        d = json.load(f)
    d["id"] = new_id
    os.makedirs(session.DIR, exist_ok=True)
    tmp = _sfile(dst_sid) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, separators=(",", ":"))
    os.replace(tmp, _sfile(dst_sid))


def _snapshot(c, vid):
    os.makedirs(_snap_dir(c["id"]), exist_ok=True)
    dst = os.path.join(_snap_dir(c["id"]), vid + ".json")
    shutil.copyfile(_sfile(c["session"]), dst)
    return dst


def _bbox(points):
    pts = list(points)
    if not pts:
        return None
    return [min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts)]


def _union(a, b):
    if not a:
        return b
    if not b:
        return a
    return [min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]), max(a[4], b[4]), max(a[5], b[5])]


def diff_blocks(old, new):
    """(added, removed, changed, positions that differ)"""
    pos = [p for p in set(old) | set(new) if old.get(p) != new.get(p)]
    added = sum(1 for p in pos if p not in old)
    removed = sum(1 for p in pos if p not in new)
    return added, removed, len(pos) - added - removed, pos


def _inside(p, box):
    return all(box[i] <= p[i] <= box[i + 3] for i in range(3))


def scope_box(part):
    b = part and part.get("bbox")
    if not b:
        return None
    return [b[0] - SCOPE_PAD, b[1] - SCOPE_PAD, b[2] - SCOPE_PAD, b[3] + SCOPE_PAD, b[4] + SCOPE_PAD, b[5] + SCOPE_PAD]


def _size_of(blocks):
    if not blocks:
        return [0, 0, 0]
    b = _bbox(blocks)
    return [b[3] - b[0] + 1, b[4] - b[1] + 1, b[5] - b[2] + 1]


def _check_of(blocks):
    if not blocks:
        return {"total": 0, "text": "Nothing built yet"}
    found = checks.run(blocks)
    return {"total": checks.total(found), "text": checks.summary(found) if found else "No problems"}


# ------------------------------------------------------------------ parsing the AI's answer
_BLOCK = re.compile(r"```[ \t]*(questions|plan|status)[ \t]*\r?\n(.*?)```", re.S | re.I)


def _json_of(raw):
    raw = raw.strip()
    try:
        return json.loads(raw)
    except ValueError:
        pass
    for o, c in (("[", "]"), ("{", "}")):
        i, j = raw.find(o), raw.rfind(c)
        if 0 <= i < j:
            try:
                return json.loads(raw[i:j + 1])
            except ValueError:
                continue
    return None


def parse_reply(text):
    """(clean text, questions, plan, status). Missing or broken blocks give None; the clean text has the blocks removed."""
    found = {}
    for m in _BLOCK.finditer(text or ""):
        found.setdefault(m.group(1).lower(), _json_of(m.group(2)))
    clean = _BLOCK.sub("", text or "").strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    questions = None
    q = found.get("questions")
    if isinstance(q, dict):
        q = q.get("questions")
    if isinstance(q, list):
        questions = []
        for i, item in enumerate(q[:MAX_QUESTIONS], 1):
            if not isinstance(item, dict) or not str(item.get("text") or "").strip():
                continue
            ch = [str(x).strip()[:60] for x in (item.get("choices") or []) if str(x).strip()][:6]
            questions.append({"id": str(item.get("id") or f"q{i}")[:20], "text": str(item["text"]).strip()[:200],
                              "choices": ch, "answer": None})
    plan = None
    p = found.get("plan")
    if isinstance(p, dict):
        p = p.get("plan") or p.get("parts")
    if isinstance(p, list):
        plan = []
        for i, item in enumerate(p[:20], 1):
            name = item if isinstance(item, str) else (item or {}).get("name") if isinstance(item, dict) else None
            if str(name or "").strip():
                pid = str(item.get("id") or f"p{i}") if isinstance(item, dict) else f"p{i}"
                plan.append({"id": pid[:20], "name": str(name).strip()[:100]})
    status = found.get("status") if isinstance(found.get("status"), dict) else None
    return clean, questions or None, plan or None, status


# ------------------------------------------------------------------ the AI turn
CHAT_RULES = """
## Chat rules (you are talking with the user in a chat panel; the build session already exists)
- The user message tells you the session id. Never call start_build or save_build; use build_step, view, check, walk_test and undo on that session.
- On a NEW request, before building: if something important is unclear (size, what to build on, style), ask at most 3 short questions and build nothing yet.
  Write them as a fenced block, each with 2 to 4 choices the user can click:
  ```questions
  [{"id":"size","text":"How big?","choices":["About 100x100","200x200","Bigger"]}]
  ```
  Otherwise (or after the user answered) give the plan: 3 to 8 parts in the order you will build them:
  ```plan
  [{"id":"p1","name":"Terrain: hill + ground cover"},{"id":"p2","name":"Castle walls"}]
  ```
  Keep part names short, plain words. Then build part 1 in the same turn.
- Build ONE part per turn unless the user asks you to continue or build everything. Call check after each part and fix what it finds.
  End the turn with a short plain-words reply (what you built, what is next) and a status block:
  ```status
  {"done":["p1"],"title":"Hill castle"}
  ```
  "done" lists the plan part ids that are finished now.
- When the message says "Scope", change ONLY blocks inside that box and nothing else, keep everything outside exactly as it is. Say what you changed.
- Never write the blocks of a questions, plan or status block anywhere else. Do not paste build scripts in your reply.
- Never end a turn with problems you did not try to fix: after each part call check, fix what it lists, check again.
- A message that starts with "Automatic improvement" comes from the server, not the user: fix exactly the listed problems,
  change nothing else, call check, and answer in one short sentence (no questions, plan or status block).
"""


def system_prompt(text=""):
    from . import lessons, mcp_server
    out = mcp_server._skill_text() + "\n\n---\n\nYou have only the BlockForge session tools (and Read for a reference image).\n"
    lines = lessons.for_ai(40) if hasattr(lessons, "for_ai") else lessons.top(40)
    if lines:
        out += "\n## Lessons from earlier builds\n" + "\n".join("- " + ln for ln in lines) + "\n"
    style = loop.style_for(text)
    if style:
        out += f"\n## Style sheet: {style}\n" + lessons.for_style(style).strip() + "\n"
    return out + CHAT_RULES


def _plan_text(plan):
    if not plan:
        return "(no plan yet)"
    return "\n".join(f"{p['id']}: {p['name']} [{p.get('status', 'pending')}]" for p in plan)


def user_message(c, text, part=None, speaker="The user now says"):
    hist = [m for m in c["messages"][:-1] if m.get("text") and not m.get("status")][-HISTORY_MESSAGES:]
    lines = [("User" if m["role"] == "user" else "You") + ": " + m["text"][:600].replace("\n", " ") for m in hist]
    out = f"Session id: {c['session']}\n"
    if c.get("terrain"):
        out += "The session already holds the user's own terrain (loaded from their file). Build on it and never clear it.\n"
    if c.get("size"):
        out += f"Wanted size: {c['size']}\n"
    out += "\nChat so far:\n" + ("\n".join(lines) or "(this is the first message)") + "\n\nPlan:\n" + _plan_text(c["plan"]) + "\n"
    box = scope_box(part)
    if part:
        out += f"\nScope: part {part['id']} \"{part['name']}\"."
        if box:
            out += (f" Only change blocks with x {box[0]}..{box[3]}, y {box[1]}..{box[4]}, z {box[2]}..{box[5]} "
                    "(session coordinates). Everything outside stays exactly as it is.")
        out += "\n"
    return out + f"\n{speaker}:\n" + text.strip()


def _run_claude(system, user, sid, model, usage, exe, log, cid=None):
    """One claude -p run on the session tools. Returns the AI's final text."""
    from .engine import EngineError
    work = tempfile.mkdtemp(prefix="blockforge_chat_")
    try:
        tools = [t for t in loop.TOOLS if t not in ("start_build", "save_build")]
        allowed = ",".join([loop.PREFIX + t for t in tools] + ["Read"])
        banned = ",".join(loop.PREFIX + t for t in ("create_build", "update_build", "app_open", "app_close", "export_build",
                                                    "start_build", "save_build"))
        cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--model", model, "--system-prompt", system,
               "--mcp-config", loop.mcp_config(work), "--strict-mcp-config", "--tools", "Read", "--allowedTools", allowed,
               "--disallowedTools", banned, "--max-turns", str(loop.MAX_TURNS), "--no-session-persistence"]
        proc = loop._spawn(cmd, work, dict(os.environ))
        _PROCS[cid] = proc
        proc.stdin.write(user.encode("utf-8"))
        proc.stdin.close()
        timer = threading.Timer(loop.TIMEOUT, proc.kill)
        timer.start()
        res, uses, last_text = None, {}, ""
        try:
            for raw in proc.stdout:
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                msg = ev.get("message")
                content = msg.get("content") if isinstance(msg, dict) else None
                if ev.get("type") == "assistant" and isinstance(content, list):
                    for ct in [x for x in content if isinstance(x, dict)]:
                        if ct.get("type") == "tool_use":
                            uses[ct.get("id")] = ct.get("name", "")
                            line = loop._describe(ct.get("name", ""), ct.get("input") or {})
                            if line:
                                log(line)
                        elif ct.get("type") == "text" and ct.get("text"):
                            last_text = ct["text"]
                elif ev.get("type") == "user" and isinstance(content, list):
                    for ct in content:
                        if isinstance(ct, dict) and ct.get("type") == "tool_result" and \
                                uses.get(ct.get("tool_use_id"), "").endswith("check"):
                            m = re.search(r"(\d+) problem", loop._text_of(ct.get("content")))
                            log("Checks: " + (f"{m.group(1)} problems" if m else "no problems"))
                elif ev.get("type") == "result":
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
        if res.get("is_error"):
            msg = str(res.get("result") or res.get("error") or res)
            if "login" in msg.lower():
                raise EngineError("Claude Code isn't signed in. Open Settings and click 'Sign in to Claude'.")
            if "limit" in msg.lower():
                raise EngineError("You've hit your Claude usage limit for now: " + msg[:300])
            raise EngineError("Claude returned an error: " + msg[:800])
        return str(res.get("result") or last_text or "")
    finally:
        _PROCS.pop(cid, None)
        shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------ chat state
def _msg(c, role, text, **extra):
    m = {"id": uuid.uuid4().hex[:8], "role": role, "text": text, "time": time.time(), **extra}
    c["messages"].append(m)
    c["updated"] = m["time"]
    return m


def _new_version(c, note, parent, branch, part_id=None, change=None, blocks=None, tiles_check=None):
    c["counter"] = c.get("counter", 0) + 1
    vid = f"v{c['counter']}"
    snap = _snapshot(c, vid)
    blocks = blocks if blocks is not None else _blocks_of(c["session"])
    v = {"id": vid, "n": c["counter"], "note": note[:120], "parent": parent, "branch": branch, "snapshot": snap,
         "session": c["session"], "time": time.time(), "blocks": len(blocks), "size": _size_of(blocks),
         "check": tiles_check or _check_of(blocks), "part_id": part_id, "kept": False,
         "plan": [dict(p) for p in c["plan"]], **(change or {})}
    c["versions"].append(v)
    c["head"] = vid
    return v


def _version(c, vid):
    for v in c["versions"]:
        if v["id"] == vid:
            return v
    raise ChatError(f"There is no version {vid}.")


def create(prompt, size=None, terrain_build_id=None):
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ChatError("Tell it what to build first.")
    s = session.start(prompt[:60], str(size or "")[:200])
    terrain = None
    if terrain_build_id:
        d = store.get_blocks(terrain_build_id)                       # KeyError -> 404
        s.blocks = exporters.from_dict(d)
        s.tiles = {(x, y, z): t for x, y, z, t in d.get("tiles") or []}
        s.save()
        terrain = terrain_build_id
    cid = uuid.uuid4().hex[:10]
    c = {"id": cid, "title": prompt[:50], "created": time.time(), "updated": time.time(), "session": s.id,
         "size": str(size or "")[:200], "terrain": terrain, "messages": [], "plan": [], "versions": [], "head": None,
         "branch": "main", "branches": ["main"], "counter": 0, "saved": [], "cost_usd": 0.0}
    _msg(c, "user", prompt)
    _new_version(c, "Start" + (" (your terrain)" if terrain else ""), None, "main", blocks=s.blocks)
    save_state(c)
    return c


def view(cid):
    """The full state for the UI."""
    c = load(cid)
    v = _version(c, c["head"])
    c["busy"] = cid in _BUSY
    c["info"] = {"blocks": v["blocks"], "size": v["size"], "check": v["check"], "version": v["id"]}
    for x in c["versions"]:
        x.pop("snapshot", None)
        x.pop("plan", None)
    return c


def _set_status(c, running_part=None):
    for p in c["plan"]:
        if p.get("status") == "building":
            p["status"] = "pending"
    if running_part:
        running_part["status"] = "building"


def answer(cid, question_id, choice):
    """Records a clicked choice. Returns the text to send to the AI when every question of that message is answered, else None."""
    choice = str(choice or "").strip()[:200]
    if not choice:
        raise ChatError("Pick one of the choices.")
    with _lock(cid):
        c = load(cid)
        for m in reversed(c["messages"]):
            qs = m.get("questions") or []
            q = next((q for q in qs if q["id"] == question_id), None)
            if q:
                if q.get("answer") is not None:
                    raise ChatError("That question is already answered.")
                q["answer"] = choice
                text = None
                if all(x.get("answer") is not None for x in qs):
                    text = "; ".join(f"{x['text']} {x['answer']}" for x in qs)
                    _msg(c, "user", text)
                save_state(c)
                return text
        raise KeyError(question_id)


def run_turn(cid, text, part_id=None, log=print, add_user=True):
    """One user request: an AI turn, then (when the blocks it changed have problems or low quality) up to CHAT_ROUNDS
    improvement turns on its own. Returns {"chat_id", "version" (the first turn's, or None if no blocks changed), "rounds"}."""
    with _GUARD:
        if cid in _BUSY:
            raise ChatError("It is still working on your last message.")
        _BUSY.add(cid)
    try:
        res = _one_turn(cid, text, part_id, log, add_user)
        res["rounds"] = 0
        if res["version"] and not res.get("paused"):
            res["rounds"] = _auto_improve(cid, log)
        return res
    finally:
        _BUSY.discard(cid)
        _PAUSED.discard(cid)


def improve(cid, log=print):
    """The "Keep improving" button: up to CHAT_ROUNDS more improvement rounds, quality included, without a user message."""
    with _GUARD:
        if cid in _BUSY:
            raise ChatError("It is still working on your last message.")
        _BUSY.add(cid)
    try:
        return {"chat_id": cid, "version": None, "rounds": _auto_improve(cid, log, force=True)}
    finally:
        _BUSY.discard(cid)
        _PAUSED.discard(cid)


def _look(cid, force=False):
    """Checks + quality of the chat's session now. Quality counts once the plan is finished (a half-built house has no roof yet)."""
    c = load(cid)
    s = session.load(c["session"])
    finished = force or all(p.get("status") == "done" for p in c["plan"])
    return selfimprove.assess(s.blocks, s.ground(), s.terrain_blocks, s.size_hint, with_quality=finished)


def _auto_improve(cid, log, rounds=selfimprove.CHAT_ROUNDS, force=False):
    """Improvement rounds until 0 problems and quality >= QUALITY_MIN, or `rounds` are used. Returns the rounds run."""
    first = last = _look(cid, force)
    if first["ok"]:
        return 0
    used, paused, last_version = 0, False, None
    for k in range(1, rounds + 1):
        if cid in _PAUSED:
            _PAUSED.discard(cid)
            paused = True
            break
        line = selfimprove.status_line(last, k, rounds)
        with _lock(cid):
            c = load(cid)
            _msg(c, "system", line, status=True, round=k)
            save_state(c)
        log(line)
        try:
            r = _one_turn(cid, selfimprove.improve_message(last, k, rounds), None, log, False, improve=line)
        except Exception:                                   # the error is already in the chat; keep the hand-back below
            break
        used = k
        last_version = r["version"] or last_version
        if r.get("paused"):
            paused = True
            break
        last = _look(cid, force)
        if last["ok"]:
            break
    text, done = selfimprove.hand_back(first, last, used, rounds)
    if paused:
        text = "Paused while improving. " + text
    with _lock(cid):
        c = load(cid)
        extra = {"improved": {"before": {"problems": first["problems"], "quality": first["qtotal"]},
                              "after": {"problems": last["problems"], "quality": last["qtotal"]}, "rounds": used}}
        if last_version:
            v = _version(c, last_version)
            extra["change"] = {k: v[k] for k in ("added", "removed", "changed", "stayed") if k in v}
            extra["change"].update({"version": v["id"], "part": "Improvements", "kept": None})
        if not done:
            extra["keep_improving"] = True
        _msg(c, "ai", text, **extra)
        save_state(c)
    log("Improved: " + text)
    return used


def _one_turn(cid, text, part_id, log, add_user, improve=None):
    """One AI turn (the busy flag is held by the caller). improve = the status line of an automatic improvement round."""
    from . import engine
    from .engine import EngineError
    try:
        with _lock(cid):
            c = load(cid)
            part = next((p for p in c["plan"] if p["id"] == part_id), None) if part_id else None
            if part_id and not part:
                raise ChatError("That part is not in the plan.")
            if add_user:
                _msg(c, "user", text, **({"scope": {"part_id": part["id"], "name": part["name"]}} if part else {}))
            if improve:
                pass                                        # the plan is not touched by an improvement round
            elif not part:
                _set_status(c, next((p for p in c["plan"] if p.get("status") != "done"), None))
            else:
                _set_status(c)
            save_state(c)
        settings = store.load_settings()
        model = settings.get("model") or "claude-opus-5-5"
        usage = engine.Usage("claude_chat", model)
        before = _blocks_of(c["session"])
        log("Asking Claude (via Claude Code)...")
        try:
            exe = engine.find_claude()
            if exe is None:
                raise EngineError("Claude Code isn't installed, so the chat can't build yet.")
            reply = _run_claude(system_prompt(text), user_message(c, text, part, "Automatic improvement message" if improve else "The user now says"),
                                c["session"], model, usage, exe, log, cid)
        except Exception as e:
            if cid in _PAUSED:                              # Pause: keep what was built so far as a version
                _PAUSED.discard(cid)
                with _lock(cid):
                    res = _finish_turn(load(cid), before, "Paused. What was built so far is kept.", part, text, usage, log, improve)
                    res["paused"] = True
                    return res
            with _lock(cid):
                c = load(cid)
                _set_status(c)
                _msg(c, "system", "That didn't work: " + str(e)[:300], error=True)
                save_state(c)
            raise
        with _lock(cid):
            c = load(cid)
            return _finish_turn(c, before, reply, part, text, usage, log, improve)
    finally:
        pass


def _finish_turn(c, before, reply, part, text, usage, log, improve=None):
    sid = c["session"]
    s = session.load(sid)
    after = s.blocks
    box = scope_box(part)
    reverted = 0
    if box:                                              # a scoped change never leaves its part
        _, _, _, pos = diff_blocks(before, after)
        outside = [p for p in pos if not _inside(p, box)]
        if outside:
            fix = []
            for p in outside:
                fix.append([p[0], p[1], p[2], after.get(p), before.get(p)])
                if before.get(p) is None:
                    s.blocks.pop(p, None)
                    s.tiles.pop(p, None)
                else:
                    s.blocks[p] = before[p]
            s.history.append({"note": "kept the rest of the build as it was", "code": "", "diff": fix, "entities": 0, "time": time.time()})
            s.save()
            after = s.blocks
            reverted = len(outside)
    added, removed, changed, pos = diff_blocks(before, after)
    clean, questions, plan, status = parse_reply(reply)
    if improve:                                          # an improvement round never changes the plan or asks questions
        questions = plan = status = None
    if plan:
        old = {p["id"]: p for p in c["plan"]}
        c["plan"] = [{**p, **{k: old[p["id"]][k] for k in ("status", "bbox") if k in old.get(p["id"], {})}} for p in plan]
        for p in c["plan"]:
            p.setdefault("status", "pending")
    if status and isinstance(status.get("title"), str) and status["title"].strip():
        c["title"] = status["title"].strip()[:60]
    done_ids = [str(x) for x in (status or {}).get("done", [])] if isinstance(status, dict) else []
    version, target = None, None
    if part:
        target = next(p for p in c["plan"] if p["id"] == part["id"])
        if pos:
            target["bbox"] = _union(target.get("bbox"), _bbox(pos))
    elif improve:
        pass
    else:
        marked = [p for p in c["plan"] if p["id"] in done_ids]
        if not marked and pos:                              # no status block: the first open part is the one it built
            marked = [p for p in c["plan"] if p.get("status") != "done"][:1]
        for p in marked:
            p["status"] = "done"
        if marked and pos:
            target = marked[-1]
            if len(marked) == 1:
                target["bbox"] = _bbox(pos)
    if pos:
        note = improve or (f"{part['name']}: {text.strip()[:50]}" if part else (target["name"] if target else text.strip()[:60]))
        change = {"added": added, "removed": removed, "changed": changed, "stayed": len(before) - removed - changed}
        if reverted:
            change["kept_outside"] = reverted
        version = _new_version(c, note, c["head"], c["branch"], part_id=target and target["id"], change=change, blocks=after)
    _set_status(c)
    rec = usage.record()
    c["cost_usd"] = round(c.get("cost_usd", 0.0) + (rec.get("cost_usd") or 0), 4)
    extra = {}
    if questions:
        extra["questions"] = questions
    if version:
        extra["change"] = {k: version[k] for k in ("added", "removed", "changed", "stayed", "kept_outside") if k in version}
        extra["change"].update({"version": version["id"], "part": (part or {}).get("name") or version["note"], "kept": None})
    if not clean:
        clean = "Done." if version else "OK."
    if not improve:                                      # the improvement rounds speak once, in the hand-back message
        _msg(c, "ai", clean, **extra)
    save_state(c)
    log("Done: " + (f"{added} added, {removed} removed, {changed} changed." if version else "no blocks changed."))
    return {"chat_id": c["id"], "version": version and version["id"]}


def pause(cid):
    """Stops the running AI turn. Blocks it already placed stay (they become a version)."""
    proc = _PROCS.get(cid)
    if cid not in _BUSY:
        raise ChatError("It is not working on anything right now.")
    _PAUSED.add(cid)                                     # between two AI turns (checking, improving) the flag stops the next round
    if proc is not None:
        proc.kill()
    return {"ok": True}


def keep(cid, vid):
    with _lock(cid):
        c = load(cid)
        v = _version(c, vid)
        v["kept"] = True
        for m in c["messages"]:
            if (m.get("change") or {}).get("version") == vid:
                m["change"]["kept"] = True
        save_state(c)
    return view(cid)


def _restore(c, v):
    _copy_session(v["snapshot"], c["session"], c["session"])
    c["plan"] = [dict(p) for p in v.get("plan", [])]


def undo(cid):
    """Back one version. The undone version stays in the history."""
    with _lock(cid):
        if cid in _BUSY:
            raise ChatError("It is still working. Wait for it to finish.")
        c = load(cid)
        v = _version(c, c["head"])
        if not v["parent"]:
            raise ChatError("Nothing to undo.")
        parent = _version(c, v["parent"])
        _restore(c, parent)
        c["head"] = parent["id"]
        for m in c["messages"]:
            if (m.get("change") or {}).get("version") == v["id"]:
                m["change"]["kept"] = False
        _msg(c, "system", f"Went back to {parent['id']} ({parent['note']}). {v['id']} is still in the history.")
        save_state(c)
    return view(cid)


def checkout(cid, vid):
    """A new branch that starts at version `vid`: a new session with its blocks. Nothing is deleted."""
    with _lock(cid):
        if cid in _BUSY:
            raise ChatError("It is still working. Wait for it to finish.")
        c = load(cid)
        v = _version(c, vid)
        s = session.start(c["title"], c.get("size", ""))
        _copy_session(v["snapshot"], s.id, s.id)
        c["session"] = s.id
        c["plan"] = [dict(p) for p in v.get("plan", [])]
        branch = f"b{len(c['branches']) + 1}"
        c["branches"].append(branch)
        c["branch"] = branch
        nv = _new_version(c, f"Branch from {v['id']} ({v['note']})", v["id"], branch, tiles_check=v["check"])
        _msg(c, "system", f"Started a new branch {branch} from {v['id']}. The other versions are still in the history.")
        save_state(c)
    return view(cid)


def history(cid):
    c = load(cid)
    path, vid = set(), c["head"]
    byid = {v["id"]: v for v in c["versions"]}
    while vid:
        path.add(vid)
        vid = byid[vid]["parent"]
    out = []
    for v in sorted(c["versions"], key=lambda v: -v["n"]):
        out.append({**{k: v.get(k) for k in ("id", "n", "note", "parent", "branch", "time", "blocks", "size", "part_id",
                                              "added", "removed", "changed", "kept")},
                    "current": v["id"] == c["head"], "on_path": v["id"] in path, "check": v["check"]})
    return {"head": c["head"], "branch": c["branch"], "branches": c["branches"], "versions": out}


def _snap_blocks(v):
    with open(v["snapshot"], encoding="utf-8") as f:
        return {(x, y, z): st for x, y, z, st in json.load(f)["blocks"]}


def compare(cid, vid):
    """What is different between version `vid` and the current version."""
    c = load(cid)
    a, b = _version(c, vid), _version(c, c["head"])
    added, removed, changed, pos = diff_blocks(_snap_blocks(a), _snap_blocks(b))     # a -> now
    return {"version": vid, "now": b["id"], "added": added, "removed": removed, "changed": changed,
            "bbox": _bbox(pos), "same": not pos}


def blocks_for_viewer(cid):
    c = load(cid)
    s = session.load(c["session"])
    return exporters.to_dict(s.blocks, s.tiles, s.entities)


def save_build(cid, title=None):
    """Saves the current version to the gallery. Returns {"id", "title", "share"}."""
    with _lock(cid):
        c = load(cid)
        try:
            meta, _text = session.save(session.load(c["session"]), title or c["title"])
        except session.SessionError as e:
            raise ChatError(str(e)) from None
        c["saved"].append(meta["id"])
        _msg(c, "system", f"Saved to My builds: {meta['title']}.")
        save_state(c)
    try:
        link = share.best_link(meta["id"])
    except (OSError, ValueError, KeyError) as e:
        link = {"url": None, "note": str(e)}
    return {"id": meta["id"], "title": meta["title"], "share": link}
