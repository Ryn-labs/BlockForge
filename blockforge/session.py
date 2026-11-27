"""Step-by-step build sessions for the AI tools: place a part, look at it, check it, fix it, then save.

A session is {(x, y, z): state} plus an undo history, kept on disk (DATA/sessions/<id>.json) so the tool server
can restart without losing the build. Every step runs a small buildkit script on top of what is already there,
through the same sandbox as a full build script, so shapes behave exactly the same."""
import json
import os
import re
import time
import uuid

from . import checks, describe, mods, placement, render, sandbox, share, store

DIR = os.path.join(store.DATA, "sessions")
MAX_LINES = 15


class SessionError(Exception):
    pass


def _path(sid):
    if not re.fullmatch(r"[0-9a-f]{6,32}", str(sid or "")):
        raise SessionError(f"'{sid}' is not a session id. Start one with start_build.")
    return os.path.join(DIR, sid + ".json")


class Session:
    def __init__(self, sid, title="Untitled build", size_hint="", blocks=None, tiles=None, entities=None, history=None):
        self.id = sid
        self.title = title
        self.size_hint = size_hint
        self.blocks = blocks or {}
        self.tiles = tiles or {}
        self.entities = entities or []          # [x, y, z, entity]
        self.history = history or []            # [{"note", "code", "diff": [[x,y,z,old,new]], "entities": n, "time"}]

    def save(self):
        os.makedirs(DIR, exist_ok=True)
        data = {"id": self.id, "title": self.title, "size_hint": self.size_hint,
                "blocks": [[x, y, z, s] for (x, y, z), s in self.blocks.items()],
                "tiles": [[x, y, z, t] for (x, y, z), t in self.tiles.items()],
                "entities": self.entities, "history": self.history}
        tmp = _path(self.id) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, _path(self.id))


def start(title="Untitled build", size_hint=""):
    s = Session(uuid.uuid4().hex[:10], str(title or "Untitled build")[:80], str(size_hint or "")[:200])
    s.save()
    return s


def load(sid):
    try:
        with open(_path(sid), encoding="utf-8") as f:
            d = json.load(f)
    except OSError:
        raise SessionError(f"There is no build session '{sid}'. Start one with start_build.") from None
    return Session(d["id"], d.get("title"), d.get("size_hint", ""), {(x, y, z): s for x, y, z, s in d["blocks"]},
                   {(x, y, z): t for x, y, z, t in d.get("tiles", [])}, d.get("entities", []), d.get("history", []))


def _fmt(p):
    return f"({p[0]}, {p[1]}, {p[2]})"


def _short(st):
    return (st or "air").split("[", 1)[0].replace("minecraft:", "")


def _size_words(blocks):
    if not blocks:
        return "empty"
    lo = [min(p[i] for p in blocks) for i in range(3)]
    hi = [max(p[i] for p in blocks) for i in range(3)]
    return (f"x {lo[0]}..{hi[0]}, y {lo[1]}..{hi[1]}, z {lo[2]}..{hi[2]} "
            f"({hi[0] - lo[0] + 1} x {hi[1] - lo[1] + 1} x {hi[2] - lo[2] + 1})")


# ------------------------------------------------------------------ steps
def step(s, code, note=""):
    """Run `code` on top of the session's blocks. Returns a plain-words report."""
    try:
        popts = mods.build_opts()[2]
    except Exception:                                    # noqa: BLE001 - settings problems must not stop building
        popts = {}
    base = (dict(s.blocks), dict(s.tiles)) if s.blocks else None
    try:
        new, meta = sandbox.run_safe(code, placement_opts=popts, base=base)
    except sandbox.ScriptError as e:
        raise SessionError("That step failed, nothing was changed:\n" + str(e)) from None
    old = s.blocks
    diff = [[x, y, z, old.get((x, y, z)), new.get((x, y, z))]
            for (x, y, z) in sorted(set(old) | set(new), key=lambda q: (q[1], q[0], q[2]))
            if old.get((x, y, z)) != new.get((x, y, z))]
    added = sum(1 for d in diff if d[3] is None)
    removed = sum(1 for d in diff if d[4] is None)
    changed = len(diff) - added - removed                 # a block that was there and is now a different block
    new_ents = [list(e) for e in (meta.get("entities") or [])]
    s.blocks = new
    s.tiles = sandbox.tiles_of(meta)
    s.entities += new_ents
    s.history.append({"note": str(note or "")[:200], "code": code, "diff": diff, "entities": len(new_ents),
                      "time": time.time()})
    s.save()
    lines = [f"Step {len(s.history)} done: {added} added, {changed} replaced, {removed} removed. "
             f"The build now has {len(new):,} blocks, {_size_words(new)}."]
    if changed:
        ex = [d for d in diff if d[3] is not None and d[4] is not None][:3]
        lines.append(f"{changed} existing block{'s were' if changed != 1 else ' was'} overwritten, e.g. "
                     + "; ".join(f"{_fmt(d[:3])} {_short(d[3])} -> {_short(d[4])}" for d in ex)
                     + ". Fine if you meant it.")
    for w in (meta.get("warnings") or [])[:4]:
        lines.append("Warning: " + str(w))
    for fx in (meta.get("fixes") or [])[:3]:
        lines.append("Auto-fixed: " + str(fx))
    lines += _check_lines(new, MAX_LINES)
    return "\n".join(lines)


def _check_lines(blocks, limit):
    found = checks.run(blocks)
    if not found:
        return ["Checks: no problems found."]
    out = ["Checks: " + checks.summary(found) + "."]
    out += ["- " + f["text"] for f in found[:limit - 2]]
    more = len(found) - (limit - 2)
    if more > 0:
        out.append(f"...and {more} more (use check to see them all).")
    return out[:limit]


def check_text(s):
    if not s.blocks:
        return "The build is empty, nothing to check."
    found = checks.run(s.blocks)
    if not found:
        return "No problems found: no floating parts, buried or jumpy paths, wrong stairs or blocked doors."
    return "Checks: " + checks.summary(found) + ".\n" + "\n".join("- " + f["text"] for f in found)


# ------------------------------------------------------------------ undo / history
def undo(s, steps=1):
    steps = max(1, int(steps or 1))
    if not s.history:
        raise SessionError("Nothing to undo.")
    n = 0
    while n < steps and s.history:
        e = s.history.pop()
        for x, y, z, old, _new in e["diff"]:
            if old is None:
                s.blocks.pop((x, y, z), None)
            else:
                s.blocks[(x, y, z)] = old
        if e.get("entities"):
            del s.entities[-e["entities"]:]
        n += 1
    s.tiles = {p: t for p, t in s.tiles.items() if p in s.blocks}
    s.save()
    return (f"Undid {n} step{'s' if n != 1 else ''}. The build has {len(s.blocks):,} blocks, {_size_words(s.blocks)}, "
            f"{len(s.history)} step{'s' if len(s.history) != 1 else ''} left.")


def history_text(s):
    if not s.history:
        return "No steps yet."
    rows = []
    for i, e in enumerate(s.history, 1):
        add = sum(1 for d in e["diff"] if d[3] is None)
        rem = sum(1 for d in e["diff"] if d[4] is None)
        rows.append(f"{i}. {e['note'] or '(no note)'}: +{add} -{rem} ~{len(e['diff']) - add - rem}")
    return "\n".join(rows)


def describe_text(s):
    if not s.blocks:
        return "The build is empty."
    return describe.base_brief(s.blocks, has_picture=False)


# ------------------------------------------------------------------ view
def view(s, sides=None):
    """[(side, png bytes)]"""
    if not s.blocks:
        raise SessionError("The build is empty, there is nothing to look at yet.")
    sides = [x.lower() for x in (sides or ["north", "east", "south", "west", "top"])]
    bad = [x for x in sides if x not in render.SIDES]
    if bad:
        raise SessionError("Unknown side " + ", ".join(bad) + ". Use north, east, south, west or top.")
    return [(x, render.render_side(s.blocks, x)) for x in sides]


# ------------------------------------------------------------------ walk test
def _cells(path):
    """Orthogonally connected (x, z) cells along the straight lines between the points."""
    pts = []
    for p in path or []:
        if not (isinstance(p, (list, tuple)) and len(p) == 2):
            raise SessionError("path must be a list of [x, z] points, like [[2, 10], [2, 4], [8, 4]].")
        pts.append((int(round(p[0])), int(round(p[1]))))
    if not pts:
        raise SessionError("path is empty.")
    cells = [pts[0]]
    for (x1, z1), (x2, z2) in zip(pts, pts[1:]):
        n = max(abs(x2 - x1), abs(z2 - z1))
        for i in range(1, n + 1):
            c = (round(x1 + (x2 - x1) * i / n), round(z1 + (z2 - z1) * i / n))
            last = cells[-1]
            if c == last:
                continue
            if c[0] != last[0] and c[1] != last[1]:
                cells.append((c[0], last[1]))                # no diagonal steps: go round the corner
            cells.append(c)
    return cells


def _walk_from(B, col_y, cells, start_y):
    """Walk the cells starting on surface start_y of the first column. Returns the list of problems."""
    g = B.get
    problems, prev, prev_cell, feet_now = [], None, None, None
    for i, cell in enumerate(cells):
        stand = [y for y in sorted(col_y.get(cell, []), reverse=True)
                 if checks.is_solid(B[(cell[0], y, cell[1])]) or checks.is_step(B[(cell[0], y, cell[1])])]
        if not stand:
            problems.append(f"No floor at x={cell[0]}, z={cell[1]}: nothing to stand on in that column.")
            prev = None
            continue
        if i == 0:
            y = start_y
        elif feet_now is None:
            y = stand[0]
        else:
            def dist(q):
                return abs(checks.feet(B[(cell[0], q, cell[1])], q) - feet_now)
            free = [q for q in stand if not any(checks.blocks_head(g((cell[0], q + h, cell[1]))) for h in (1, 2))]
            near = min(free, key=lambda q: (dist(q), -q)) if free else None
            # a surface with room that is at most one block away is the way on (a jump if it is too high);
            # otherwise report the surface you would really be standing on
            y = near if near is not None and dist(near) <= 1.0 else min(stand, key=lambda q: (dist(q), -q))
        st = B[(cell[0], y, cell[1])]
        here = (cell[0], y, cell[1])
        for h in (1, 2):
            if checks.blocks_head(g((cell[0], y + h, cell[1]))):
                problems.append(f"Not enough head room at {_fmt(here)}: {_short(g((cell[0], y + h, cell[1])))} is {h} above "
                                f"the floor, you need 2 free blocks.")
                break
        if prev is not None:
            dv = (cell[0] - prev_cell[0], cell[1] - prev_cell[1])
            ha = checks.feet_dir(B[prev], prev[1], dv, "out")
            hb = checks.feet_dir(st, y, dv, "in")
            if abs(hb - ha) > 0.6:
                problems.append(f"Jump of {abs(hb - ha):g} blocks going from {_fmt(prev)} to {_fmt(here)}. "
                                f"A rise of 1 needs a bottom stair facing uphill; more needs several steps.")
        prev, prev_cell, feet_now = here, cell, checks.feet(st, y)
    return problems


def walk(s, path):
    """Walk the path on the surfaces you can stand on. The start surface is the one that gives the fewest problems
    (so a walk from a doorstep does not start on the roof above it)."""
    B = s.blocks
    cells = _cells(path)
    col_y = {}
    for (x, y, z) in B:
        col_y.setdefault((x, z), []).append(y)
    starts = [y for y in sorted(col_y.get(cells[0], []), reverse=True)
              if checks.is_solid(B[(cells[0][0], y, cells[0][1])]) or checks.is_step(B[(cells[0][0], y, cells[0][1])])][:8]
    if starts:
        problems = min((_walk_from(B, col_y, cells, y0) for y0 in starts), key=len)
    else:
        problems = _walk_from(B, col_y, cells, 0)
    head = (f"Walked {len(cells)} cell{'s' if len(cells) != 1 else ''} from x={cells[0][0]}, z={cells[0][1]} "
            f"to x={cells[-1][0]}, z={cells[-1][1]}.")
    if not problems:
        return head + " No problems: floor everywhere, no jumps, 2 free blocks of head room."
    shown = problems[:MAX_LINES]
    return (head + f" {len(problems)} problem{'s' if len(problems) != 1 else ''}:\n"
            + "\n".join("- " + p for p in shown)
            + (f"\n...and {len(problems) - len(shown)} more." if len(problems) > len(shown) else ""))


# ------------------------------------------------------------------ save
def save(s, title=None):
    """Final placement pass, then store the build (source claude_chat). Returns (meta, preview text)."""
    if not s.blocks:
        raise SessionError("The build is empty, there is nothing to save.")
    pack, version, popts = mods.build_opts()
    blocks = dict(s.blocks)
    final = placement.process(blocks, final=True, **popts)             # nothing impossible gets saved
    found = checks.run(blocks)
    code = "\n\n".join((e.get("code") or "").strip() for e in s.history if e.get("code")) or None
    ents = [tuple(e) for e in s.entities]
    m = store.save_build(blocks, title or s.title, prompt=s.size_hint or "", code=code, source="claude_chat",
                         model="claude-code-chat", fixes=final["fixed"], warnings=final["problems"],
                         data_version=mods.data_version(version), modpack=(pack or {}).get("name"),
                         tiles={p: t for p, t in s.tiles.items() if p in blocks}, entities=ents or None,
                         checks={"total": checks.total(found), "by_check": checks.counts(found)})
    return m, share.chat_text(m["id"])
