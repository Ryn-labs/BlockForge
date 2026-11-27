"""Terrain as the base of a new build: load it, the ground height map, and the counts of what a build changed.

A terrain is a normal {(x, y, z): state} block dict (an imported .schem/.litematic or a stored build). In a session its
positions are remembered (session.terrain, with the original states in session.terrain_blocks) so the checks and the
reports can tell land from what the AI built on it."""
import os

from . import checks

NATURAL_TOP_SKIP = ("_leaves", "_log", "_wood", "_stem", "_hyphae")     # trees are not ground
MAX_CELLS = 64                                                          # ground map cells per side before it gets coarser


class TerrainError(Exception):
    pass


def load(ref):
    """Blocks of a terrain: `ref` is the id of a stored build or the path of a .schem/.litematic/.nbt file."""
    from . import exporters, store
    ref = str(ref or "").strip().strip('"')
    if not ref:
        raise TerrainError("terrain is empty. Give a build id or the path of a .schem/.litematic file.")
    if os.path.isfile(ref):
        with open(ref, "rb") as f:
            blocks = exporters.import_file(f.read())
    else:
        try:
            blocks = exporters.from_dict(store.get_blocks(ref))
        except (OSError, ValueError, KeyError):
            raise TerrainError(f"terrain '{ref[:80]}' is neither a file nor a stored build id.") from None
    if not blocks:
        raise TerrainError("The terrain has no blocks.")
    return blocks


def is_ground_block(state):
    """A block that counts as the land surface: solid, but not a leaf or tree wood."""
    n = checks.name(state)
    return checks.is_solid(state) and not n.endswith(NATURAL_TOP_SKIP)


def ground_top(blocks, terrain=None):
    """{(x, z): y of the top ground block}. Tree wood and leaves of the ORIGINAL terrain are skipped (a tree is not
    ground); a log wall the AI built is. `terrain` = {pos: original state}."""
    top = {}
    terrain = terrain or {}
    for p, s in blocks.items():
        if not checks.is_solid(s):
            continue
        if checks.name(s).endswith(NATURAL_TOP_SKIP) and terrain.get(p) == s:
            continue
        c = (p[0], p[2])
        if p[1] > top.get(c, -10 ** 9):
            top[c] = p[1]
    return top


class Ground:
    """What the checks need to know about the land: `top` {(x, z): y} and `terrain` {pos: original state}."""

    def __init__(self, blocks, terrain):
        self.terrain = terrain
        self.top = ground_top({p: s for p, s in blocks.items() if terrain.get(p) == s}, terrain)   # the land as it is now

    def is_land(self, blocks, p):
        """An original, untouched ground block (not a leaf or a trunk)."""
        s = self.terrain.get(p)
        return s is not None and blocks.get(p) == s and is_ground_block(s) and p[1] <= self.top.get((p[0], p[2]), -1)

    def untouched(self, blocks, p):
        s = self.terrain.get(p)
        return s is not None and blocks.get(p) == s


def bounds(blocks):
    xs = [p[0] for p in blocks]
    zs = [p[2] for p in blocks]
    ys = [p[1] for p in blocks]
    return min(xs), min(zs), max(xs), max(zs), min(ys), max(ys)


def ground_text(top, x1=None, z1=None, x2=None, z2=None, step=None):
    """The ground height map as rows of numbers (max 64 x 64 cells; a bigger area is sampled every `step` blocks)."""
    if not top:
        return "There is no ground here (no solid blocks)."
    bx1, bz1 = min(c[0] for c in top), min(c[1] for c in top)
    bx2, bz2 = max(c[0] for c in top), max(c[1] for c in top)
    x1, z1 = bx1 if x1 is None else int(x1), bz1 if z1 is None else int(z1)
    x2, z2 = bx2 if x2 is None else int(x2), bz2 if z2 is None else int(z2)
    x1, x2, z1, z2 = min(x1, x2), max(x1, x2), min(z1, z2), max(z1, z2)
    need = max(-(-(x2 - x1 + 1) // MAX_CELLS), -(-(z2 - z1 + 1) // MAX_CELLS), 1)
    step = max(int(step or 1), need)
    xs = list(range(x1, x2 + 1, step))
    zs = list(range(z1, z2 + 1, step))
    vals = [top[(x, z)] for z in zs for x in xs if (x, z) in top]
    if not vals:
        return f"There is no ground inside x {x1}..{x2}, z {z1}..{z2}."
    w = max(len(str(max(vals))), len(str(min(vals))), 1)
    lines = [f"Ground height (y of the top solid block, trees skipped), x {x1}..{x2} across, z {z1}..{z2} down, "
             f"one number every {step} block{'s' if step != 1 else ''}; '.' = no ground. "
             f"Lowest {min(vals)}, highest {max(vals)}.",
             "x: " + " ".join(str(x).rjust(w) for x in xs)]
    for z in zs:
        lines.append(f"z{z}: " + " ".join((str(top[(x, z)]) if (x, z) in top else ".").rjust(w) for x in xs))
    return "\n".join(lines)


def summary(blocks, terrain, top):
    """Short facts for describe / start_build."""
    x1, z1, x2, z2, y1, y2 = bounds(terrain)
    hs = list(top.values())
    hi = max(top, key=top.get)
    return (f"Terrain: x {x1}..{x2}, z {z1}..{z2}, y {y1}..{y2} ({len(terrain):,} blocks). Ground height {min(hs)}..{max(hs)}, "
            f"highest point at x={hi[0]}, z={hi[1]} (y={top[hi]}). Build ON it: use ground() for the height map, plan_layout() to "
            f"place parts, and cut/fill as little as you can.")


def change_counts(diff, terrain, orig_top):
    """Count the terrain changes of one step. diff = [[x, y, z, old, new]]. Returns {"dug", "replaced", "filled"}:
    dug = a terrain block removed, replaced = a terrain block swapped for another block, filled = a block placed in
    a hole of the land (at or below the original ground surface where the land has no block)."""
    dug = replaced = filled = 0
    for x, y, z, old, new in diff:
        p = (x, y, z)
        if p in terrain:
            if new is None:
                dug += 1
            elif old is not None and old != new:
                replaced += 1
            elif old is None:
                filled += 1                                      # refilling a cell that was dug before
        elif old is None and new is not None and (x, z) in orig_top and y <= orig_top[(x, z)]:
            filled += 1
    return {"dug": dug, "replaced": replaced, "filled": filled}


def change_words(c, total=None):
    if not (c["dug"] or c["replaced"] or c["filled"]):
        return ""
    t = f"Terrain: dug {c['dug']:,} blocks, replaced {c['replaced']:,}, filled {c['filled']:,}."
    if total and total != c:
        t += f" In all so far: dug {total['dug']:,}, replaced {total['replaced']:,}, filled {total['filled']:,}."
    return t
