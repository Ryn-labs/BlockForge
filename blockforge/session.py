"""Step-by-step build sessions for the AI tools: place a part, look at it, check it, fix it, then save.

A session is {(x, y, z): state} plus an undo history, kept on disk (DATA/sessions/<id>.json) so the tool server
can restart without losing the build. Every step runs a small buildkit script on top of what is already there,
through the same sandbox as a full build script, so shapes behave exactly the same."""
import json
import os
import re
import time
import uuid

from . import checks, describe, mods, placement, render, sandbox, share, store, terrain as terr

DIR = os.path.join(store.DATA, "sessions")
MAX_LINES = 15


class SessionError(Exception):
    pass


def _path(sid):
    if not re.fullmatch(r"[0-9a-f]{6,32}", str(sid or "")):
        raise SessionError(f"'{sid}' is not a session id. Start one with start_build.")
    return os.path.join(DIR, sid + ".json")


class Session:
    def __init__(self, sid, title="Untitled build", size_hint="", blocks=None, tiles=None, entities=None, history=None,
                 terrain_blocks=None, terrain_top=None):
        self.id = sid
        self.title = title
        self.size_hint = size_hint
        self.blocks = blocks or {}
        self.tiles = tiles or {}
        self.entities = entities or []          # [x, y, z, entity]
        self.history = history or []            # [{"note", "code", "diff": [[x,y,z,old,new]], "entities": n, "time"}]
        self.terrain_blocks = terrain_blocks or {}   # the land the build started on: {pos: original state} (own file)
        self.terrain = set(self.terrain_blocks)      # its positions
        self.terrain_top = terrain_top or {}         # original ground height {(x, z): y}

    def ground(self):
        """The Ground object the checks use, or None when the build did not start on terrain."""
        return terr.Ground(self.blocks, self.terrain_blocks) if self.terrain_blocks else None

    def save_terrain(self):
        d = {"blocks": [[x, y, z, s] for (x, y, z), s in self.terrain_blocks.items()],
             "top": [[x, z, y] for (x, z), y in self.terrain_top.items()]}
        with open(_terrain_path(self.id), "w", encoding="utf-8") as f:
            json.dump(d, f, separators=(",", ":"))

    def save(self):
        os.makedirs(DIR, exist_ok=True)
        data = {"id": self.id, "title": self.title, "size_hint": self.size_hint,
                "blocks": [[x, y, z, s] for (x, y, z), s in self.blocks.items()],
                "tiles": [[x, y, z, t] for (x, y, z), t in self.tiles.items()],
                "entities": self.entities, "history": self.history, "terrain": bool(self.terrain_blocks)}
        tmp = _path(self.id) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, _path(self.id))


def _terrain_path(sid):
    return os.path.join(DIR, sid + ".terrain.json")


def start(title="Untitled build", size_hint="", terrain=None):
    """terrain = id of a stored build or the path of a .schem/.litematic file: the session starts on that land."""
    s = Session(uuid.uuid4().hex[:10], str(title or "Untitled build")[:80], str(size_hint or "")[:200])
    if terrain:
        try:
            land = terr.load(terrain)
        except terr.TerrainError as e:
            raise SessionError(str(e)) from None
        s.terrain_blocks = dict(land)
        s.terrain = set(land)
        s.blocks = dict(land)
        s.terrain_top = terr.ground_top(land, land)
        os.makedirs(DIR, exist_ok=True)
        s.save_terrain()
    s.save()
    return s


def load(sid):
    try:
        with open(_path(sid), encoding="utf-8") as f:
            d = json.load(f)
    except OSError:
        raise SessionError(f"There is no build session '{sid}'. Start one with start_build.") from None
    tb, top = None, None
    if d.get("terrain"):
        with open(_terrain_path(sid), encoding="utf-8") as f:
            td = json.load(f)
        tb = {(x, y, z): s for x, y, z, s in td["blocks"]}
        top = {(x, z): y for x, z, y in td["top"]}
    return Session(d["id"], d.get("title"), d.get("size_hint", ""), {(x, y, z): s for x, y, z, s in d["blocks"]},
                   {(x, y, z): t for x, y, z, t in d.get("tiles", [])}, d.get("entities", []), d.get("history", []), tb, top)


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
def _popts():
    try:
        return mods.build_opts()[2]
    except Exception:                                    # noqa: BLE001 - settings problems must not stop building
        return {}


def _run(s, code, popts):
    base = (dict(s.blocks), dict(s.tiles)) if s.blocks else None
    try:
        return sandbox.run_safe(code, placement_opts=popts, base=base)
    except sandbox.ScriptError as e:
        raise SessionError("That step failed, nothing was changed:\n" + str(e)) from None


def _diff(old, new):
    return [[x, y, z, old.get((x, y, z)), new.get((x, y, z))]
            for (x, y, z) in sorted(set(old) | set(new), key=lambda q: (q[1], q[0], q[2]))
            if old.get((x, y, z)) != new.get((x, y, z))]


def terrain_total(s):
    """Terrain changes of all steps still in the history."""
    tot = {"dug": 0, "replaced": 0, "filled": 0}
    for e in s.history:
        for k, v in (e.get("terrain") or {}).items():
            tot[k] = tot.get(k, 0) + v
    return tot


def _commit(s, new, tiles, new_ents, diff, note, code, lines):
    """Store a finished step in the session and build the plain-words report."""
    added = sum(1 for d in diff if d[3] is None)
    removed = sum(1 for d in diff if d[4] is None)
    changed = len(diff) - added - removed                 # a block that was there and is now a different block
    s.blocks = new
    s.tiles = tiles
    s.entities += new_ents
    entry = {"note": str(note or "")[:200], "code": code, "diff": diff, "entities": len(new_ents), "time": time.time()}
    tc = terr.change_counts(diff, s.terrain, s.terrain_top) if s.terrain else None
    if tc and any(tc.values()):
        entry["terrain"] = tc
    s.history.append(entry)
    s.save()
    out = [f"Step {len(s.history)} done: {added} added, {changed} replaced, {removed} removed. "
           f"The build now has {len(new):,} blocks, {_size_words(new)}."]
    if tc and any(tc.values()):
        out.append(terr.change_words(tc, terrain_total(s)))
    over = [d for d in diff if d[3] is not None and d[4] is not None and (d[0], d[1], d[2]) not in s.terrain]
    if over:
        out.append(f"{len(over)} existing block{'s were' if len(over) != 1 else ' was'} overwritten, e.g. "
                   + "; ".join(f"{_fmt(d[:3])} {_short(d[3])} -> {_short(d[4])}" for d in over[:3])
                   + ". Fine if you meant it.")
    out += lines
    out += _check_lines(new, MAX_LINES, s.ground())
    return "\n".join(out)


def _meta_lines(meta, prefix=""):
    out = []
    for w in (meta.get("warnings") or [])[:4]:
        out.append(prefix + "Warning: " + str(w))
    for fx in (meta.get("fixes") or [])[:3]:
        out.append(prefix + "Auto-fixed: " + str(fx))
    return out


def step(s, code, note=""):
    """Run `code` on top of the session's blocks. Returns a plain-words report."""
    new, meta = _run(s, code, _popts())
    diff = _diff(s.blocks, new)
    return _commit(s, new, sandbox.tiles_of(meta), [list(e) for e in (meta.get("entities") or [])], diff, note, code,
                   _meta_lines(meta))


MAX_PARTS = 4


def step_parts(s, parts, note=""):
    """Run several independent snippets at once (max 4 in parallel, each on the blocks as they are now), then merge.
    If two parts change the same cell the first part keeps it and the clash is reported."""
    from concurrent.futures import ThreadPoolExecutor
    if not isinstance(parts, list) or not parts:
        raise SessionError("parts must be a list of {note, code}.")
    items = []
    for i, p in enumerate(parts, 1):
        if not isinstance(p, dict) or not str(p.get("code") or "").strip():
            raise SessionError(f"Part {i} has no code.")
        items.append((str(p.get("note") or f"part {i}")[:80], p["code"]))
    popts = _popts()
    results = [None] * len(items)

    def work(i):
        try:
            results[i] = _run(s, items[i][1], popts)
        except SessionError as e:
            results[i] = e

    with ThreadPoolExecutor(max_workers=min(MAX_PARTS, len(items))) as ex:
        list(ex.map(work, range(len(items))))
    old = s.blocks
    new = dict(old)
    tiles = dict(s.tiles)
    owner, lines, ents, failed, clashes = {}, [], [], [], []
    for i, (pnote, _code) in enumerate(items):
        r = results[i]
        if isinstance(r, SessionError):
            failed.append(f"Part {i + 1} ({pnote}) failed and was skipped: {str(r).split(chr(10), 1)[-1][:300]}")
            continue
        blocks_i, meta = r
        n_clash = 0
        for pos in set(old) | set(blocks_i):
            st = blocks_i.get(pos)
            if old.get(pos) == st:
                continue
            if pos in owner:
                if new.get(pos) != st:
                    n_clash += 1
                    if len(clashes) < 4:
                        clashes.append(f"{_fmt(pos)}: part {owner[pos] + 1} ({items[owner[pos]][0]}) kept over part {i + 1} ({pnote})")
                continue
            owner[pos] = i
            if st is None:
                new.pop(pos, None)
            else:
                new[pos] = st
        if n_clash:
            lines.append(f"Conflict: part {i + 1} ({pnote}) touched {n_clash} cell{'s' if n_clash != 1 else ''} "
                         f"already changed by an earlier part; the earlier part was kept.")
        for k, tl in sandbox.tiles_of(meta).items():
            if owner.get(k) == i:
                tiles[k] = tl
        ents += [list(e) for e in (meta.get("entities") or [])]
        lines += _meta_lines(meta, f"Part {i + 1}: ")
    if len(failed) == len(items):
        raise SessionError("Every part failed, nothing was changed:\n" + "\n".join(failed))
    if clashes:
        lines.insert(0, "Clashes, e.g. " + "; ".join(clashes))
    lines = failed + lines
    tiles = {p: tl for p, tl in tiles.items() if p in new}
    diff = _diff(old, new)
    code = "\n\n".join(c for _n, c in items)
    note = note or "; ".join(n_ for n_, _c in items)
    head = f"Ran {len(items) - len(failed)} of {len(items)} parts in parallel. "
    return head + _commit(s, new, tiles, ents, diff, note, code, lines)


def _check_lines(blocks, limit, ground=None):
    found = checks.run(blocks, ground=ground)
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
    found = checks.run(s.blocks, ground=s.ground())
    if not found:
        return "No problems found: no floating parts, buried or jumpy paths, wrong stairs or blocked doors."
    return "Checks: " + checks.summary(found) + ".\n" + "\n".join("- " + f["text"] for f in found)


def ground_text(s, x1=None, z1=None, x2=None, z2=None, step=None):
    """The ground height map of the build as it is now."""
    if not s.blocks:
        return "The build is empty, there is no ground yet."
    top = terr.ground_top(s.blocks, s.terrain_blocks)
    return terr.ground_text(top, x1, z1, x2, z2, step)


def plan_layout_text(s, area, parts, street_width=5):
    """(text, plan dict) of layout.plan on the current ground."""
    from . import layout
    if not s.blocks:
        raise SessionError("The build is empty, there is no ground to plan on. Start the build with terrain.")
    top = terr.ground_top(s.blocks, s.terrain_blocks)
    try:
        plan = layout.plan(top, area, parts, street_width)
    except layout.LayoutError as e:
        raise SessionError(str(e)) from None
    return layout.plan_text(plan), plan


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
    if s.terrain:
        top = terr.ground_top(s.blocks, s.terrain_blocks)
        span = max(max(c[0] for c in top) - min(c[0] for c in top), max(c[1] for c in top) - min(c[1] for c in top)) + 1
        out = [terr.summary(s.blocks, s.terrain_blocks, top),
               terr.change_words(terrain_total(s)) or "Terrain: untouched so far.",
               terr.ground_text(top, step=max(1, -(-span // 32)))]
        built = {p: st for p, st in s.blocks.items() if s.terrain_blocks.get(p) != st}
        out.append("What you built so far: " + (f"{_size_words(built)}, {len(built):,} blocks." if built else "nothing yet."))
        if built:
            out.append(describe.describe(built, budget=6000))
        return "\n".join(out)
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
    found = checks.run(blocks, ground=s.ground())
    code = "\n\n".join((e.get("code") or "").strip() for e in s.history if e.get("code")) or None
    ents = [tuple(e) for e in s.entities]
    m = store.save_build(blocks, title or s.title, prompt=s.size_hint or "", code=code, source="claude_chat",
                         model="claude-code-chat", fixes=final["fixed"], warnings=final["problems"],
                         data_version=mods.data_version(version), modpack=(pack or {}).get("name"),
                         tiles={p: t for p, t in s.tiles.items() if p in blocks}, entities=ents or None,
                         checks={"total": checks.total(found), "by_check": checks.counts(found)})
    return m, share.chat_text(m["id"])
