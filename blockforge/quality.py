"""Building quality score: is this a good-looking house, or a blocky box?

score(blocks, size=None, prompt=None) -> {"total": 0-100 or None, "building": bool, "parts": {part: 0-100},
                             "findings": [plain sentences with coordinates], "fixes": {part: [what to do, with coordinates]}}

Only buildings are scored: something with at least one closed room (walls on all four sides, a roof over it and 2 blocks
of head room). Bridges, trees, terrain, statues and walls get total None (neutral, never gated).

The thirteen parts and their weights (docs/QUALITY.md has the rules behind the numbers):
  contrast 15   on the render: a light wall fill (oak, birch, stripped logs, plaster) against the log frame, most of the
                wall seen from outside light; one dark material everywhere is low
  looks 15      on the render: light walls, a coloured (not near-black or grey) roof, a colour histogram close to the
                nearest reference house (blockforge/data/ref_palette.json)
  shape 20      on the render: several gables and roof heights from every side (no long single ridge), a taller central
                block with lower wings either side of the entrance, no straight wall over 9 blocks, a gable, porch or
                stair at the entrance (a small house needs no wings); a big house with no shape is capped (SHAPE_CAP)
  storeys 10    2+ floors (a small house, hut or cottage may have 1), height against length: long and low is low
  windows 10    glass share of every facade, framed (shutters, box, sill), big windows (4+ panes together)
  balcony 8     outdoor floors above the ground floor with a railing (balconies, terraces), an outside stair up
  roof_style 8  a roof colour that stands out from the walls (teal, green, red ...), roof planes at several heights
  facade 4      wall depth: posts, frames and beams sticking out 1+ from the wall plane; flat runs longer than 5 = penalty
  roof 3        pitched stair/slab roof, eaves overhanging 1+, a trim or ridge in a second material; flat = big penalty
  massing 2     main volume + wings/porch/balcony/annex, more than one roof height; a single box is low
  palette 2     3-6 materials with roles: frame (logs), wall fill, a different roof, accents; 1 material or 10 random = low
  detail 2      windows per facade metre, framed windows, shutters/boxes/lanterns/fences/pots, a chimney
  surroundings 1   a path to the door, garden/fence/farm/terrace/light around the house
"Render" = the four side views drawn with render.py's block colours (render.nearest), house cells only. A house that
reads dark there is held below the gate (DARK_CAP) unless the prompt asks for a dark look (dark_asked).
"""
import bisect
import collections
import colorsys
import json
import math
import os

from .checks import PATH_BLOCKS, THIN_NAMES, THIN_SUFFIXES, name as _name, props as _props
from .render import block_color, nearest

QUALITY_MIN = 60                     # save_build and the script engine refuse/fix a building below this (one place)
WEIGHTS = {"contrast": 15, "looks": 15, "storeys": 10, "windows": 10, "balcony": 8, "roof_style": 8, "shape": 20,
           "facade": 4, "roof": 3, "massing": 2, "palette": 2, "detail": 2, "surroundings": 1}
LABELS = {"facade": "Facade depth", "roof": "Roof", "massing": "Massing", "palette": "Palette", "detail": "Detail",
          "surroundings": "Surroundings", "contrast": "Wall contrast", "storeys": "Storeys", "windows": "Windows",
          "balcony": "Balconies", "roof_style": "Roof colour and layers", "looks": "Looks (colours)"}
SMALL_WORDS = ("tiny", "small", "little", "hut", "cottage", "cabin", "shed")
SMALL_ROOMS = 36                     # a building with this many room columns or fewer is small whatever the prompt says
MIN_ROOM_COLUMNS = 4                 # a 2 x 2 room with 2 blocks of head room is the smallest building
REACH = 40                           # a wall or roof further away than this does not close a room

WOODS = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "bamboo", "crimson", "warped",
         "pale_oak")
FLOWERS = {"poppy", "dandelion", "blue_orchid", "allium", "azure_bluet", "red_tulip", "orange_tulip", "white_tulip",
           "pink_tulip", "oxeye_daisy", "cornflower", "lily_of_the_valley", "wither_rose", "sunflower", "lilac", "rose_bush",
           "peony", "torchflower", "pink_petals", "pitcher_plant", "spore_blossom", "open_eyeblossom", "closed_eyeblossom",
           "wildflowers", "leaf_litter", "cactus_flower"}
CROPS = {"wheat", "carrots", "potatoes", "beetroots", "melon_stem", "pumpkin_stem", "attached_melon_stem",
         "attached_pumpkin_stem", "sweet_berry_bush", "sugar_cane", "cocoa", "nether_wart", "torchflower_crop",
         "pitcher_crop"}
GROUND = {"grass_block", "dirt", "coarse_dirt", "podzol", "rooted_dirt", "mycelium", "farmland", "moss_block", "mud",
          "sand", "red_sand", "clay", "snow", "dirt_path"}
PLANTS = {"short_grass", "tall_grass", "grass", "fern", "large_fern", "dead_bush", "azalea", "flowering_azalea", "bush",
          "firefly_bush", "vine", "lily_pad", "seagrass", "tall_seagrass", "kelp", "kelp_plant", "bamboo", "moss_carpet",
          "glow_lichen", "hanging_roots", "big_dripleaf", "small_dripleaf", "cave_vines", "cave_vines_plant"} | FLOWERS
FLUIDS = {"water", "lava", "bubble_column"}
AIR = {"air", "cave_air", "void_air", "light", "structure_void", "barrier"}
SOFT_SUFFIX = ("_carpet", "_bed", "lantern", "torch", "_candle", "candle", "_pressure_plate", "_button", "_sign", "_banner",
               "flower_pot", "rail", "_head", "_skull")
SOFT = {"redstone_wire", "tripwire", "lever", "cobweb", "string", "item_frame", "painting", "end_rod", "chain"}
LIGHTS = ("lantern", "torch", "campfire", "sea_lantern", "glowstone", "shroomlight", "froglight", "candle", "end_rod",
          "redstone_lamp")
PROPS_ = {"barrel", "hay_block", "composter", "bell", "lectern", "cauldron", "water_cauldron", "beehive", "bee_nest",
          "grindstone", "anvil", "scaffolding", "decorated_pot", "chiseled_bookshelf", "ladder", "chain", "iron_bars",
          "smoker", "blast_furnace", "brewing_stand", "pumpkin", "carved_pumpkin", "jack_o_lantern", "melon"}
CHIMNEY_STONE = ("bricks", "cobblestone", "stone_bricks", "mud_bricks", "deepslate", "stone", "andesite", "tuff",
                 "blackstone", "granite", "nether_bricks", "terracotta")
DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
SIDE = {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}


# ------------------------------------------------------------------ block kinds
def _leaf(n):
    return n.endswith("_leaves") or n in ("azalea_leaves", "flowering_azalea_leaves")


def is_nature(n):
    """Ground, plants, crops, fluids and leaves: not part of the building's structure."""
    return (n in GROUND or n in PLANTS or n in CROPS or n in FLUIDS or _leaf(n) or n.endswith("_sapling")
            or n.endswith("_mushroom") or n.endswith("_coral"))


def is_soft(n):
    """Small things that hang or stand inside rooms: they never close a room or make a wall."""
    return n in SOFT or n.startswith("potted_") or n.endswith(SOFT_SUFFIX)


_KIND = {}


def kind(n):
    k = _KIND.get(n)
    if k is None:
        if len(_KIND) > 50000:
            _KIND.clear()
        k = _KIND[n] = _kind(n)
    return k


def _kind(n):
    if n in AIR:
        return "air"
    if n in CROPS or n == "farmland":
        return "farm"
    if is_nature(n):
        return "nature"
    if n.endswith("_door"):
        return "door"
    if "glass" in n:
        return "glass"
    if n.endswith("_trapdoor"):
        return "trapdoor"
    if n.endswith("_stairs"):
        return "stairs"
    if n.endswith("_slab"):
        return "slab"
    if n.endswith(("_fence", "_fence_gate", "_wall")) or n == "iron_bars":
        return "fence"
    if any(t in n for t in LIGHTS):
        return "light"
    if n.startswith("potted_") or n == "flower_pot":
        return "pot"
    if n.endswith(("_banner", "_wall_banner")):
        return "banner"
    if n.endswith(("_sign", "_hanging_sign")):
        return "sign"
    if n in PROPS_ or n.endswith("_button"):
        return "prop"
    if (n.endswith(("_log", "_wood", "_hyphae")) or n.startswith("stripped_") or n.endswith("_pillar")
            or (n.endswith("_stem") and n not in CROPS) or n == "bamboo_block"):
        return "frame"
    if is_soft(n):
        return "soft"
    return "other" if n in THIN_NAMES or n.endswith(THIN_SUFFIXES) else "full"


def mkey(n):
    """The material a block is made of: oak_stairs, oak_slab and oak_fence are all oak_planks."""
    for suf in ("_stairs", "_slab", "_fence_gate", "_fence", "_wall", "_trapdoor", "_door", "_button", "_pressure_plate",
                "_hanging_sign", "_wall_sign", "_sign"):
        if n.endswith(suf):
            n = n[: -len(suf)]
            break
    if n in WOODS:
        return n + "_planks"
    if n.endswith(("_brick", "_tile")) or n == "brick":
        return n + "s"
    return n


def _fmt(p):
    return "(" + ", ".join(str(v) for v in p) + ")"


# ------------------------------------------------------------------ geometry
def _dilate(cols, r):
    """Every (x, z) within r (a square) of a column of `cols`: grown along x, then along z."""
    if r <= 0:
        return set(cols)
    rng = range(-r, r + 1)
    row = {(x + a, z) for (x, z) in cols for a in rng}
    return {(x, z + c) for (x, z) in row for c in rng}


def _components(cols):
    cols, out = set(cols), []
    while cols:
        start = cols.pop()
        comp, todo = [start], [start]
        while todo:
            x, z = todo.pop()
            for a in (-1, 0, 1):
                for c in (-1, 0, 1):
                    q = (x + a, z + c)
                    if q in cols:
                        cols.remove(q)
                        comp.append(q)
                        todo.append(q)
        out.append(comp)
    return out


def _between(sorted_list, v, reach):
    """True when the sorted list has a value below v and one above v, each within reach."""
    i = bisect.bisect_left(sorted_list, v)
    return 0 < i < len(sorted_list) and v - sorted_list[i - 1] <= reach and sorted_list[i] - v <= reach


class _Model:
    """Everything the parts need, worked out once."""

    def __init__(self, blocks):
        N, S, K = {}, {}, {}
        nk = {}                                                      # state -> (name, kind): few states, many blocks
        for p, s in blocks.items():
            got = nk.get(s)
            if got is None:
                n = _name(s)
                got = nk[s] = (n, kind(n))
            if got[0] in AIR:
                continue
            N[p] = got[0]
            S[p] = s
            K[p] = got[1]
        self.N, self.S, self.K = N, S, K
        st = {p for p, k in self.K.items() if k not in ("nature", "farm", "soft")}
        self.ST = st
        rx, rz, cy = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
        for (x, y, z) in st:
            rx[(y, z)].append(x)
            rz[(y, x)].append(z)
            cy[(x, z)].append(y)
        for d in (rx, rz, cy):
            for v in d.values():
                v.sort()
        self.cy = cy
        def covered(x, y, z):
            ys = cy.get((x, z))
            return bool(ys) and ys[-1] > y and ys[bisect.bisect_right(ys, y)] - y <= 24

        def closed(x, y, z, dx, dz):
            # walk to the wall under the roof: a ray that leaves the covered area first is open (a porch, a gap)
            for k in range(1, REACH + 1):
                p = (x + dx * k, y, z + dz * k)
                if p in st:
                    return True
                if not covered(*p):
                    return False
            return False

        inside = set()
        for (y, z), xs in rx.items():
            for a, b in zip(xs, xs[1:]):
                if b - a < 2 or b - a > REACH:
                    continue
                for x in range(a + 1, b):
                    zs = rz.get((y, x))
                    if (zs and _between(zs, z, REACH) and covered(x, y, z) and closed(x, y, z, 1, 0)
                            and closed(x, y, z, -1, 0) and closed(x, y, z, 0, 1) and closed(x, y, z, 0, -1)):
                        inside.add((x, y, z))
        self.IN = {p for p in inside if (p[0], p[1] + 1, p[2]) in inside or (p[0], p[1] - 1, p[2]) in inside}
        self.I = set()
        for (x, y, z) in self.IN:
            if (x, y - 1, z) in self.IN or (x, y + 1, z) not in self.IN or (x, z) in self.I:
                continue                                             # not the bottom of a room stack
            k = 0
            while (x, y - 1 - k, z) in st and k < 4:
                k += 1
            if k < 3:                                                # a floor under it, not the top of a wall
                self.I.add((x, z))
        self.building = len(self.I) >= MIN_ROOM_COLUMNS
        if not self.building:
            return
        self.IN = {p for p in self.IN if (p[0], p[2]) in self.I}
        self.F1 = _dilate(self.I, 1)
        self.F2 = _dilate(self.I, 2)
        self.ring1 = self.F1 - self.I
        self.ring2 = self.F2 - self.F1
        self.g = min((y for (x, z) in self.F1 for y in cy.get((x, z), ())), default=0)
        self.T = {c: cy[c][-1] for c in self.F2 if c in cy}
        self.room_top = {}
        for (x, y, z) in self.IN:
            if y > self.room_top.get((x, z), -10 ** 9):
                self.room_top[(x, z)] = y
        xs = [c[0] for c in self.I]
        zs = [c[1] for c in self.I]
        self.box = (min(xs), min(zs), max(xs), max(zs))
        self.chimneys = self._chimneys()

    def top_state(self, c):
        y = self.T.get(c)
        return None if y is None else (c[0], y, c[1])

    def _chimneys(self):
        out = []
        for c in self.F2:
            y = self.T.get(c)
            if y is None or y < self.g + 4:
                continue
            nb = [self.T.get((c[0] + a, c[1] + b)) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)]
            if max((v for v in nb if v is not None), default=-10 ** 9) > y - 2:
                continue
            ys = self.cy[c]
            run, prev = 0, None
            for yy in reversed(ys):
                n = self.N[(c[0], yy, c[1])]
                if prev is not None and yy != prev - 1:
                    break
                if self.K[(c[0], yy, c[1])] == "full" and any(t in n for t in CHIMNEY_STONE):
                    run += 1
                elif run == 0 and self.K[(c[0], yy, c[1])] in ("light", "fence", "slab", "full", "frame"):
                    pass                                             # a cap (campfire, wall, slab) on top
                else:
                    break
                prev = yy
            if run >= 3:
                out.append((c[0], y, c[1]))
        return out


# ------------------------------------------------------------------ parts
def _faces(m):
    """Every outside face of the rooms: [direction, first cell outside, open/window/wall, material, depth, is frame,
    flower box]. Depth = how many blocks deep the wall is there, counted outward. Worked out once per model."""
    if getattr(m, "faces", None) is not None:
        return m.faces
    faces = []
    for (x, y, z) in m.IN:
        for d in DIRS4:
            q = (x + d[0], y, z + d[1])
            if q in m.IN:
                continue
            if any((x + d[0] * k, y, z + d[1] * k) in m.IN for k in (2, 3, 4)):
                continue                                             # an inner wall between two rooms
            k = m.K.get(q)
            if k in ("stairs", "slab"):
                continue                                             # roof slope over an attic
            if k is None or k in ("air", "soft", "nature", "farm"):
                fk = "open"
            elif k in ("glass", "door", "trapdoor", "fence"):
                fk = "window"
            else:
                fk = "wall"
            t = 0                                                    # how deep the wall is here, counted outward
            while t < 4:
                c = (q[0] + d[0] * t, y, q[2] + d[1] * t)
                if c not in m.ST or (t and m.K[c] == "stairs" and "half=top" not in m.S[c]):
                    break                                            # a roof eave in front is not wall depth
                t += 1
            box = t <= 1 and m.N.get((q[0] + d[0], y, q[2] + d[1])) in GROUND and y > m.g + 1   # a flower box
            faces.append((d, q, fk, mkey(m.N[q]) if q in m.N else "", t, k == "frame", box))
    m.faces = faces
    return faces


def _facade(m):
    faces = [list(f) for f in _faces(m)]
    total = len(faces)
    if not total:
        return 0, [], []
    base = collections.defaultdict(collections.Counter)            # the usual wall depth of each wall plane
    for f in faces:
        base[(f[0], f[1][0] if f[0][0] else f[1][2])][f[4]] += 1
    struct = 0
    for f in faces:
        b0 = base[(f[0], f[1][0] if f[0][0] else f[1][2])].most_common(1)[0][0]
        deeper = f[4] > b0
        if deeper and m.K.get((f[1][0] + f[0][0] * b0, f[1][1], f[1][2] + f[0][1] * b0)) in ("frame", "full", "stairs", "slab"):
            struct += 1                                              # a post, beam or pillar, not just a shutter
        f[4] = f[6] or deeper
    prot = sum(1 for f in faces if f[4])
    frame = sum(1 for f in faces if f[5])
    rows = collections.defaultdict(list)
    for d, q, fk, mat, pr, fr, _ in faces:
        plane = q[0] if d[0] else q[2]
        u = q[2] if d[0] else q[0]
        rows[(d, plane, q[1])].append((u, fk, mat, pr, q))
    excess, worst = 0, None
    for key, cells in rows.items():
        cells.sort()
        run, prev = [], None
        for c in cells + [(None, "", "", True, None)]:
            flat = c[1] == "wall" and not c[3]
            if flat and prev is not None and c[0] == prev[0] + 1 and c[2] == prev[2] and run:
                run.append(c)
            else:
                if len(run) > 5:
                    excess += len(run) - 5
                    if worst is None or len(run) > len(worst[1]):
                        worst = (key[0], run)
                run = [c] if flat else []
            prev = c
    s = prot / total
    ss = struct / total
    ratio = excess / total
    score = (40 * min(1, ss / 0.10) + 15 * min(1, s / 0.15) + 30 * (1 - min(1, ratio / 0.15))
             + 15 * min(1, frame / (0.1 * total)))
    find, fix = [], []
    if worst:
        d, run = worst
        a, b = run[0][4], run[-1][4]
        find.append(f"Facade: the {SIDE[d]} wall from {_fmt(a)} to {_fmt(b)} is a flat run of {len(run)} {run[0][2]} "
                    f"blocks with no post, window or step.")
        fix.append(f"On the {SIDE[d]} wall from {_fmt(a)} to {_fmt(b)}: add log posts that stick out 1 block every 3-4 "
                   f"blocks and a log beam along the floor and top lines (pattern framed_wall).")
    if ss < 0.10:
        find.append(f"Facade: only {round(100 * ss)}% of the wall surface has a post, beam or pillar sticking out of the "
                    f"wall plane (good houses: 10% or more).")
        if not worst:
            x1, z1, x2, z2 = m.box
            fix.append(f"Give the walls around x {x1 - 1}..{x2 + 1}, z {z1 - 1}..{z2 + 1} depth: log posts and beams 1 block "
                       f"out from the wall (pattern framed_wall), window boxes (pattern window_with_box).")
    return score, find, fix


def _roof(m):
    pitched = flat = 0
    mats = collections.Counter()
    for c in m.F2:
        p = m.top_state(c)
        if p is None or p[1] < m.g + 3 or p in m.chimneys:
            continue
        k = m.K[p]
        if k in ("stairs", "slab"):
            if c in m.F1 or k == "stairs":
                pitched += 1
            mats[mkey(m.N[p])] += 1
        elif k in ("full", "frame") and c in m.F1:
            flat += 1
            mats[mkey(m.N[p])] += 1
    levels = len({m.T[c] for c in m.I if c in m.T})
    slope = min(1.0, (levels - 1) / 3)
    p_share = pitched / (pitched + flat) if pitched + flat else 0.0
    pitch_score = p_share * slope
    if pitch_score < 0.5 and _crenellated(m):
        pitch_score = 0.5                                            # a battlement top: a castle style, not a bare box
    over = 0
    for c in m.ring2:
        for y in m.cy.get(c, ()):
            if y >= m.g + 3 and (c[0], y - 1, c[1]) not in m.ST:
                over += 1
                break
    over_frac = over / len(m.ring2) if m.ring2 else 0
    total = sum(mats.values())
    trim = len([k for k, v in mats.items() if v >= 0.05 * total]) >= 2 if total else False
    ridge = False
    for c in m.I:
        p = m.top_state(c)
        if p is None or c in [(q[0], q[2]) for q in m.chimneys]:
            continue
        if all(m.T.get((c[0] + a, c[1] + b), -10 ** 9) <= p[1] for a, b in DIRS4):
            st = m.S[p]
            if m.K[p] == "slab" or m.K[p] in ("full", "frame") and levels > 2 or (m.K[p] == "stairs" and "half=top" in st):
                ridge = True
                break
    planes = collections.defaultdict(set)
    for c in m.F2:
        p = m.top_state(c)
        if p is not None and m.K[p] == "stairs":
            planes[_props(m.S[p]).get("facing", "?")].add(c)
    big, big_at = 0, None
    for facing, cols in planes.items():
        for comp in _components_4(cols, m.T):
            if len(comp) > big:
                big, big_at = len(comp), (facing, min(comp))
    penalty = max(0.0, min(25.0, (big - 140) / 6))
    score = 45 * pitch_score + 25 * min(1, over_frac / 0.6) + 20 * trim + 10 * ridge - penalty
    x1, z1, x2, z2 = m.box
    top = max((m.T[c] for c in m.I if c in m.T), default=m.g)
    find, fix = [], []
    if pitch_score < 0.5:
        find.append(f"Roof: the roof over x {x1}..{x2}, z {z1}..{z2} (top y {top}) is flat or nearly flat "
                    f"({round(100 * p_share)}% stairs/slabs, {levels} height level{'s' if levels != 1 else ''}).")
        fix.append(f"Replace the flat top over x {x1}..{x2}, z {z1}..{z2} with a pitched stair roof (eaves at y {top}) "
                   f"with an overhang of 1 and a trim (pattern gable_roof_trim, hip_roof_trim or cross_gable_roof).")
    if over_frac < 0.6:
        bare = next((c for c in sorted(m.ring2) if not any(y >= m.g + 3 for y in m.cy.get(c, ()))), None)
        find.append(f"Roof: the eaves overhang the walls on only {round(100 * over_frac)}% of the outline"
                    + (f" (none at x {bare[0]}, z {bare[1]})" if bare else "") + ".")
        fix.append("Let the roof stick out 1 block past every wall (overhang=1, barge boards on the gable ends).")
    if not trim:
        find.append("Roof: one material only, no trim or ridge in a second material.")
        fix.append("Add a roof trim: the gable edges (barge boards) and the ridge in a second material, e.g. oak "
                   "stairs on a teal roof (pattern gable_roof_trim, trim='oak').")
    if penalty > 0:
        find.append(f"Roof: one roof plane of {big} blocks facing {big_at[0]} near x {big_at[1][0]}, z {big_at[1][1]} "
                    f"is very large and plain.")
        fix.append(f"Break the {big_at[0]}-facing roof plane near x {big_at[1][0]}, z {big_at[1][1]} with a cross gable "
                   f"or dormer (pattern cross_gable_roof).")
    return score, find, fix


def _crenellated(m):
    """Merlons on the wall tops: along the outline the top height steps up and down by 1 on at least half the cells."""
    tops = {c: m.T[c] for c in m.ring1 if c in m.T}
    if len(tops) < 8:
        return False
    steps = sum(1 for (x, z), y in tops.items()
                if any(abs(tops.get((x + a, z + b), y) - y) == 1 for a, b in DIRS4))
    return steps >= 0.5 * len(tops)


def _components_4(cols, T):
    cols, out = set(cols), []
    while cols:
        s = cols.pop()
        comp, todo = [s], [s]
        while todo:
            x, z = todo.pop()
            for a, b in DIRS4:
                q = (x + a, z + b)
                if q in cols and abs(T.get(q, 0) - T.get((x, z), 0)) <= 1:
                    cols.remove(q)
                    comp.append(q)
                    todo.append(q)
        out.append(comp)
    return out


def _massing(m):
    xs = [c[0] for c in m.F1]
    zs = [c[1] for c in m.F1]
    area = (max(xs) - min(xs) + 1) * (max(zs) - min(zs) + 1)
    nonrect = 1 - len(m.F1) / area
    chim = {(q[0], q[2]) for q in m.chimneys}
    ridges = collections.Counter()
    for c in m.F1:
        p = m.top_state(c)
        if p is None or c in chim or m.K[p] not in ("stairs", "slab", "full", "frame"):
            continue
        if all(m.T.get((c[0] + a, c[1] + b), -10 ** 9) <= p[1] for a in (-1, 0, 1) for b in (-1, 0, 1)
               if (c[0] + a, c[1] + b) not in chim):
            ridges[p[1]] += 1
    levels = len([y for y, n in ridges.items() if n >= 2])
    lv = 0.0 if levels <= 1 else 0.6 if levels == 2 else 1.0
    zone = _dilate(m.F1, 6) - m.F2
    attach = 0
    for c in zone:
        ys = m.cy.get(c)
        if not ys:
            continue
        if any(_leaf(m.N.get((c[0], y, c[1]), "")) for y in range(ys[0], ys[-1] + 4)):
            continue                                                 # a tree
        if any(y >= m.g + 2 and m.K[(c[0], y, c[1])] in ("full", "frame", "stairs", "slab", "trapdoor") for y in ys):
            attach += 1
    P = max(1, len(m.ring1))
    at = min(1.0, attach / (0.15 * P))
    comps = [c for c in _components(m.I) if len(c) >= 6]
    multi = 1.0 if len(comps) >= 2 else 0.0
    small = 20 if len(m.I) < 50 else 0
    score = 15 + 25 * min(1, nonrect / 0.2) + 20 * lv + 25 * at + 15 * multi + small
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    if nonrect < 0.1 and levels <= 1:
        find.append(f"Massing: the building is one box (x {x1}..{x2}, z {z1}..{z2}) with one roof height.")
        fix.append(f"Add a lower wing or annex beside the main volume at x {x1}..{x2}, z {z1}..{z2} (different roof "
                   f"height, its own gable) - an L or T plan.")
    if at < 0.5:
        find.append(f"Massing: almost nothing stands out of the walls ({attach} columns of porch, balcony, terrace or "
                    f"annex for {P} metres of wall).")
        fix.append(f"Add a porch with posts and its own roof at the door, or a balcony on supports (patterns porch, "
                   f"balcony) on the walls around x {x1 - 1}..{x2 + 1}, z {z1 - 1}..{z2 + 1}.")
    return min(100, score), find, fix


def _palette(m):
    cnt = collections.Counter()
    frame = 0
    accents = set()
    for p, n in m.N.items():
        if (p[0], p[2]) not in m.F2:
            continue
        k = m.K[p]
        if k in ("nature", "farm", "air"):
            continue
        cnt[mkey(n)] += 1
        if k == "frame":
            frame += 1
        if k in ("glass", "door", "trapdoor", "fence", "light", "pot", "banner", "sign", "prop"):
            accents.add(mkey(n) + ":" + k)
    total = sum(cnt.values()) or 1
    main = [k for k, v in cnt.items() if v >= max(4, 0.03 * total)]
    n = len(main)
    count_score = {0: 0, 1: 0, 2: 8, 3: 20, 4: 20, 5: 20, 6: 20, 7: 14, 8: 8}.get(n, 0) - (10 if n > 10 else 0)
    wall = collections.Counter()
    for c in m.ring1:
        for y in m.cy.get(c, ()):
            p = (c[0], y, c[1])
            if m.K[p] == "full" and y <= m.room_top.get(c, max((m.room_top.get((c[0] + a, c[1] + b), -1) for a in (-1, 0, 1)
                                                                    for b in (-1, 0, 1)), default=-1)):
                wall[mkey(m.N[p])] += 1
    fill = wall.most_common(1)[0][0] if wall else None
    roof = collections.Counter()
    for c in m.F1:
        p = m.top_state(c)
        if p is not None and p not in m.chimneys and m.K[p] in ("stairs", "slab", "full"):
            roof[mkey(m.N[p])] += 1
    roof_mat = roof.most_common(1)[0][0] if roof else None
    has_frame = frame >= max(6, 0.03 * total)
    distinct_roof = bool(roof_mat) and roof_mat != fill
    score = 25 * has_frame + 25 * distinct_roof + 10 * bool(fill) + 20 * min(1, len(accents) / 4) + count_score
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    if n <= 2:
        find.append(f"Palette: only {n} main material{'s' if n != 1 else ''} ({', '.join(main) or 'none'}).")
    if n > 8:
        find.append(f"Palette: {n} main materials ({', '.join(sorted(main)[:10])}) look random; keep 3-6 with clear roles.")
        fix.append("Cut the materials down to 3-6 with roles: logs for the frame, one wall fill, one roof material and "
                   "a few accents.")
    if not has_frame:
        find.append(f"Palette: no log frame (posts, beams) in the walls around x {x1}..{x2}, z {z1}..{z2}.")
        fix.append(f"Frame the walls around x {x1}..{x2}, z {z1}..{z2} with logs (corner posts, floor beams) in a different "
                   f"wood than the wall fill (pattern framed_wall).")
    if not distinct_roof:
        find.append(f"Palette: the roof is the same material as the walls ({fill or roof_mat}).")
        fix.append("Make the roof a different material from the walls (e.g. teal prismarine brick stairs with an "
                   "oak trim over birch or oak walls).")
    if len(accents) < 3:
        fix.append("Add accents: glass panes, trapdoor shutters, lanterns, fences.")
    return max(0, min(100, score)), find, fix


def _detail(m):
    P = max(1, len(m.ring1))
    glass = framed = 0
    sample_wall = None
    for c in m.ring1:
        for y in m.cy.get(c, ()):
            p = (c[0], y, c[1])
            if sample_wall is None and m.K[p] == "full":
                sample_wall = p
            if m.K[p] != "glass":
                continue
            glass += 1
            near = [(p[0] + a, p[1] + b, p[2] + d) for a, b, d in
                    ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                     (1, -1, 0), (-1, -1, 0), (0, -1, 1), (0, -1, -1))]
            if any(m.K.get(q) in ("trapdoor", "slab", "stairs", "frame", "fence", "nature", "pot") for q in near):
                framed += 1
    kinds = collections.Counter()
    for p, k in m.K.items():
        c = (p[0], p[2])
        if c not in m.F2 or (c in m.I and p[1] <= m.room_top.get(c, -10 ** 9)):
            continue                                                 # inside a room: furniture, not facade detail
        if k in ("trapdoor", "pot", "light", "fence", "banner", "sign", "prop"):
            kinds[k] += 1
        elif k == "stairs" and "half=top" in m.S[p] and p[1] > m.g:
            kinds["bracket"] += 1
        elif k == "nature" and (m.N[p] in FLOWERS or _leaf(m.N[p])) and p[1] > m.g + 1:
            kinds["planter"] += 1
    items = sum(kinds.values())
    chimney = bool(m.chimneys)
    gpm = glass / P
    score = (30 * min(1, gpm / 0.25) + 15 * (framed / glass if glass else 0) + 25 * min(1, len(kinds) / 5)
             + 15 * min(1, items / (0.5 * P)) + 15 * chimney)
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    if gpm < 0.25:
        find.append(f"Detail: {glass} window panes for {P} metres of wall (good: 1 pane per 4 metres or more).")
        fix.append(f"Add windows every 3-4 blocks on every wall around x {x1}..{x2}, z {z1}..{z2}, each with trapdoor "
                   f"shutters and a flower box (pattern window_with_box).")
    elif glass and framed / glass < 0.5:
        find.append(f"Detail: {glass - framed} of {glass} window panes have no frame, sill, shutter or box.")
        fix.append("Frame the windows: trapdoor shutters, a sill or flower box under them (pattern window_with_box).")
    if len(kinds) < 4:
        find.append(f"Detail: few kinds of outside detail ({', '.join(sorted(kinds)) or 'none'}).")
        fix.append("Hang lanterns by the door, add flower pots, fences on the porch, banners or barrels by the walls.")
    if not chimney:
        find.append("Detail: no chimney.")
        fix.append(f"Add a stone or brick chimney rising 2+ blocks above the roof near x {x2 - 1}, z {(z1 + z2) // 2} "
                   f"(pattern chimney).")
    return score, find, fix


def _doors(m):
    out = []
    for p, n in m.N.items():
        if m.K[p] != "door" or _props(m.S[p]).get("half") == "upper" or (p[0], p[2]) not in m.F2:
            continue
        f = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}.get(_props(m.S[p]).get("facing"))
        if not f:
            continue
        for d in (f, (-f[0], -f[1])):
            q = (p[0] + d[0], p[1], p[2] + d[1])
            if q not in m.IN and (p[0] - d[0], p[1], p[2] - d[1]) in m.IN:
                out.append((p, d))
    return out


def _is_pathish(n, s):
    if n in PATH_BLOCKS or n in ("dirt_path", "gravel", "packed_mud", "mud_bricks", "bricks", "smooth_stone", "sandstone",
                                 "smooth_sandstone", "stone", "andesite", "polished_andesite", "polished_granite",
                                 "polished_diorite", "deepslate_bricks", "deepslate_tiles", "tuff_bricks", "calcite"):
        return True
    if n.endswith(("_planks", "_stairs", "_slab")) and "half=top" not in s and "type=top" not in s:
        return True
    return False


def _surroundings(m):
    doors = _doors(m)
    path_ok, door_at = False, None
    for p, d in doors:
        door_at = door_at or p
        px, pz = -d[1], d[0]
        n = 0
        for k in range(1, 7):
            for w in (-1, 0, 1):
                for dy in (-1, -2, -3, 0):
                    q = (p[0] + d[0] * k + px * w, p[1] + dy, p[2] + d[1] * k + pz * w)
                    s = m.S.get(q)
                    if s and _is_pathish(m.N[q], s) and (q[0], q[1] + 1, q[2]) not in m.ST:
                        n += 1
                        break
        if n >= 4:
            path_ok = True
            break
    zone = _dilate(m.F1, 14) - m.F2
    kinds = set()
    paving = 0
    for p, n in m.N.items():
        if (p[0], p[2]) not in zone or p[1] > m.g + 5:
            continue
        k = m.K[p]
        if k == "fence":
            kinds.add("fence")
        elif k == "farm":
            kinds.add("farm")
        elif n in FLOWERS or n.endswith("_sapling") or n in ("short_grass", "tall_grass", "fern", "azalea", "bush") or _leaf(n):
            kinds.add("plants")
        elif n == "water":
            kinds.add("water")
        elif k == "light":
            kinds.add("light")
        elif n in ("hay_block", "composter"):
            kinds.add("farm")
        elif _is_pathish(n, m.S[p]) and (p[0], p[1] + 1, p[2]) not in m.ST:
            paving += 1
    if paving >= 6:
        kinds.add("paving")
    score = 30 * path_ok + 14 * min(5, len(kinds))
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    if not doors:
        find.append("Surroundings: no door to the outside found.")
        fix.append(f"Put a door in an outside wall of x {x1}..{x2}, z {z1}..{z2} (pattern doorway or porch).")
    elif not path_ok:
        p, d = doors[0]
        find.append(f"Surroundings: no path leads to the door at {_fmt(p)}.")
        fix.append(f"Lay a path (gravel, dirt path or stone) from the door at {_fmt(p)} out {SIDE[d]}ward at least 4 blocks.")
    if len(kinds) < 3:
        find.append(f"Surroundings: little around the building ({', '.join(sorted(kinds)) or 'nothing'}).")
        fix.append(f"Add a garden around x {x1 - 6}..{x2 + 6}, z {z1 - 6}..{z2 + 6}: a fence with a gate, flowers and "
                   f"bushes, a farm plot, lantern posts (patterns fence_garden, farm_plot, lantern_post).")
    return min(100, score), find, fix


# ------------------------------------------------------------------ colour, storeys, windows, balconies, roof style
WALL_KINDS = ("full", "frame", "stairs", "slab", "trapdoor", "fence")
FILL_L = 62                          # lightness from here up reads as a pale fill (birch, stripped birch, plaster), not oak
LIGHT_L = 45                         # CIE lightness from here up reads as a light wall (oak, birch, stripped logs, plaster)
LOOK_CLOSE = (0.35, 0.6)             # histogram closeness to the nearest reference: 0 points at the first, full at the second
ROW_CHROMA = 58                      # CIE chroma of a strong colour patch: poppy 70, red tulip 72, dandelion 75, cornflower 68
                                     # (grass 54, fern 48, teal roof 26, wood 25-33 stay under it)
ROW_PATCHES = 4                      # this many patches of one strong colour in one row of a side view = a row of squares
ROW_PENALTY = (10, 20)               # looks points off per row found, at most
DARK_CAP = (35, 65)                  # a house that reads dark (not asked for) scores at most 35 + 65 x brightness (_bright)


def _clamp(v):
    return max(0.0, min(1.0, v))


def colour(n):
    """RGB of a material (oak_stairs -> oak planks), from the colour table of render.py."""
    return block_color(mkey(n))


def lightness(n):
    """CIE L* (0 black .. 100 white) of a material: spruce log 18, spruce planks 38, oak planks 57, birch planks 72."""
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (v / 255 for v in colour(n))]
    yy = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return 116 * yy ** (1 / 3) - 16 if yy > 0.008856 else 903.3 * yy


def lab(rgb):
    """CIE L*a*b* (D65) of an sRGB colour (0-255 each)."""
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (v / 255 for v in rgb)]
    xyz = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2], 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2],
           0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2])
    f = [t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
         for t in (xyz[0] / 0.95047, xyz[1], xyz[2] / 1.08883)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


# Colour histograms: 4 lightness bands x 16 colour bins (grey + 15 hue sectors of 24 degrees) = 64 numbers. A colour is
# shared between the two nearest bands and hue sectors (and grey for pale colours), so a texture a little lighter or a
# hue a little off lands in the same bins. tools/ref_palette.py stores the histograms of the reference houses with this.
HIST_BANDS, HIST_HUES = 4, 15
HIST_SIZE = HIST_BANDS * (HIST_HUES + 1)
_hist_cache = {}


def _hist_bins(rgb):
    got = _hist_cache.get(rgb)
    if got is not None:
        return got
    L, a, b = lab(rgb)
    u = _clamp(L / 100) * HIST_BANDS - 0.5
    lo = int(max(0, min(HIST_BANDS - 1, u // 1)))
    hi = min(HIST_BANDS - 1, lo + 1)
    t = _clamp(u - lo) if hi != lo else 0.0
    bands = [(lo, 1 - t), (hi, t)] if hi != lo else [(lo, 1.0)]
    C = (a * a + b * b) ** 0.5
    g = _clamp((14 - C) / 8)                                         # grey share: all grey below chroma 6, none above 14
    hue = (math.degrees(math.atan2(b, a)) % 360) / (360 / HIST_HUES) - 0.5
    h0 = int(hue // 1) % HIST_HUES
    th = hue - hue // 1
    cols = [(0, g)] + ([(1 + h0, (1 - g) * (1 - th)), (1 + (h0 + 1) % HIST_HUES, (1 - g) * th)] if g < 1 else [])
    out = {}
    for band, wb in bands:
        for col, wc in cols:
            if wb * wc > 0:
                k = band * (HIST_HUES + 1) + col
                out[k] = out.get(k, 0.0) + wb * wc
    _hist_cache[rgb] = out
    return out


def colour_hist(colours):
    """Normalised 64-number colour histogram of an iterable of RGB tuples, or of a {rgb: count} dict."""
    items = colours.items() if isinstance(colours, dict) else ((c, 1) for c in colours)
    h = [0.0] * HIST_SIZE
    for rgb, n in items:
        for k, w in _hist_bins(tuple(rgb)).items():
            h[k] += w * n
    s = sum(h)
    return [v / s for v in h] if s else h


def hist_closeness(a, b):
    """1 - total variation distance: 1 = the same colour mix, 0 = nothing in common."""
    return 1 - 0.5 * sum(abs(x - y) for x, y in zip(a, b))


_refs = None


def ref_palette():
    """{name: 64-number histogram} of the reference house photos (blockforge/data/ref_palette.json, made by
    tools/ref_palette.py). The two drawn plans (refs 6 and 7) are stored too but not scored against: their flat tile
    colours, grid lines and paper are not what a house looks like."""
    global _refs
    if _refs is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ref_palette.json")
        try:
            with open(path, encoding="utf-8") as f:
                _refs = {k: v["hist"] for k, v in json.load(f)["refs"].items()
                         if len(v["hist"]) == HIST_SIZE and v.get("kind", "photo") == "photo"}
        except (OSError, ValueError, KeyError):
            _refs = {}
    return _refs


DARK_WORDS = ("dark", "gothic", "spooky", "haunted", "night", "midnight", "shadow", "sinister", "evil", "vampire", "witch",
              "necromancer", "cursed", "horror", "creepy", "grim", "stronghold", "fortress", "nether", "blackstone",
              "deepslate", "obsidian", "black", "ominous", "dracula", "villain", "crypt", "dungeon")
NOT_DARK = ("blacksmith", "blacksmiths", "nightingale")


def dark_asked(prompt=None, size=None):
    """True when the request asks for a dark look (dark, gothic, spooky, night, haunted, stronghold, blackstone ...): a
    dark house is then what was wanted, so the look parts do not ask for light walls or a coloured roof."""
    words = "".join(ch if ch.isalnum() else " " for ch in f"{prompt or ''} {size or ''}".lower()).split()
    return any(w.startswith(DARK_WORDS) and w not in NOT_DARK for w in words)


def _cdist(a, b):
    ca, cb = colour(a), colour(b)
    return sum((u - v) ** 2 for u, v in zip(ca, cb)) ** 0.5


def _hue_gap(a, b):
    """How different two materials are in hue, 0..1 (1 = 60 degrees or more apart, or one grey and one coloured)."""
    ha, sa, _ = colorsys.rgb_to_hsv(*[v / 255 for v in colour(a)])
    hb, sb, _ = colorsys.rgb_to_hsv(*[v / 255 for v in colour(b)])
    if (sa < 0.15) != (sb < 0.15):
        return 1.0
    if sa < 0.15:
        return 0.0
    d = abs(ha - hb) * 360
    return _clamp(min(d, 360 - d) / 60)


def _seen(m):
    """{material: count} of the wall surface seen from outside: the four side views of the building (its columns and 2
    round them, from the ground floor to the top of the rooms), the nearest block in every cell. Posts and beams that
    stick out hide the fill behind them. Glass, doors, lights and roof slopes are left out."""
    if getattr(m, "seen", None) is not None:
        return m.seen
    top = max(m.room_top.values())
    cells = [p for p in m.ST if (p[0], p[2]) in m.F2 and m.g < p[1] <= top]
    vis = collections.Counter()
    for axis, sign in ((0, 1), (0, -1), (2, 1), (2, -1)):
        near = {}
        for p in cells:
            key = (p[2 - axis], p[1])
            if key not in near or p[axis] * sign > near[key][axis] * sign:
                near[key] = p
        for p in near.values():
            k = m.K[p]
            if k in ("stairs", "slab") and "half=top" not in m.S[p] and "type=top" not in m.S[p]:
                continue                                             # a roof slope in front of the wall
            if k in WALL_KINDS:
                vis[mkey(m.N[p])] += 1
    m.seen = vis
    return vis


def _pct(vals, q):
    """The q-quantile (0..1) of [(value, count)] sorted by value."""
    tot = sum(n for _, n in vals)
    acc = 0
    for v, n in vals:
        acc += n
        if acc >= q * tot:
            return v
    return vals[-1][0] if vals else 0.0


def _view(m):
    """What the eye sees: the four side views of the house drawn with render.py's block colours (render.nearest: the
    nearest block in every cell; the building's columns and 2 round them, above the foundation, so no sky, ground,
    garden or trees). Each cell is roof (stairs/slabs, the top of a column 3+ up), window (glass) or wall (the rest).
    Returns a dict: wall_l (mean CIE lightness of the walls), light (share of wall cells with lightness 45+),
    frame_l / fill_l / dl (frame vs fill lightness), roof_l, roof_colour (0..1, a coloured roof; near-black or grey
    is 0), hist (64-bin colour histogram of the whole house), ref / closeness (the nearest reference house)."""
    if getattr(m, "view", None) is not None:
        return m.view
    house = {p: m.S[p] for p in m.ST if (p[0], p[2]) in m.F2 and p[1] > m.g}
    wall, roof, allc = collections.Counter(), collections.Counter(), collections.Counter()
    frame_l, fill_l = [], []
    for side in ("north", "east", "south", "west"):
        for near, p, st in nearest(house, side).values():
            k = m.K[p]
            rgb = block_color(st)
            allc[rgb] += 1
            if k == "glass":
                continue
            low = "half=top" not in st and "type=top" not in st
            if (k in ("stairs", "slab") and low) or (k in ("full", "frame") and p[1] >= m.g + 3
                                                    and m.T.get((p[0], p[2])) == p[1]):
                roof[rgb] += 1
                continue
            if k in ("door", "light", "pot", "banner", "sign", "prop", "other"):
                continue
            wall[rgb] += 1
            post = k == "frame" and not m.N[p].startswith("stripped_")   # a stripped log reads as fill, not frame
            (frame_l if post else fill_l if k in ("full", "frame") else []).append(lab(rgb)[0])
    v = {"cells": sum(allc.values()), "wall_cells": sum(wall.values()), "roof_cells": sum(roof.values())}
    wl = sorted((lab(c)[0], n) for c, n in wall.items())
    nw = max(1, v["wall_cells"])
    v["wall_l"] = sum(L * n for L, n in wl) / nw
    v["light"] = sum(n for L, n in wl if L >= LIGHT_L) / nw
    v["fill_share"] = sum(n for L, n in wl if L >= FILL_L) / nw     # pale fill: birch, stripped birch, plaster
    if len(frame_l) >= 0.05 * nw and len(fill_l) >= 0.05 * nw:
        v["frame_l"], v["fill_l"] = sum(frame_l) / len(frame_l), sum(fill_l) / len(fill_l)
    elif wl:
        v["frame_l"], v["fill_l"] = _pct(wl, 0.2), _pct(wl, 0.8)           # no log frame: the dark and light ends
    else:
        v["frame_l"] = v["fill_l"] = 0.0
    v["dl"] = abs(v["fill_l"] - v["frame_l"])
    rc = rl = 0.0
    for c, n in roof.items():
        L, a, b = lab(c)
        rc += n * _clamp(((a * a + b * b) ** 0.5 - 5) / 15) * _clamp((L - 22) / 18)
        rl += n * L
    nr = max(1, v["roof_cells"])
    v["roof_colour"], v["roof_l"] = rc / nr, rl / nr
    v["roof_mat"] = max(roof, key=roof.get) if roof else None
    v["hist"] = colour_hist(allc)
    refs = ref_palette()
    best = max(((hist_closeness(v["hist"], h), name) for name, h in refs.items()), default=(0.0, None))
    v["closeness"], v["ref"] = best
    m.view = v
    return v


def _hue_name(rgb):
    h, s_, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    deg = h * 360
    for top, word in ((15, "red"), (45, "orange"), (70, "yellow"), (160, "green"), (200, "cyan"), (255, "blue"),
                      (290, "purple"), (340, "pink"), (361, "red")):
        if deg < top:
            return word
    return "bright"


def _colour_rows(m):
    """Rows of saturated same-colour patches along a facade, on the four side views of the house WITH its plants (the
    nearest block in every cell): e.g. red flowers under every window, which read as a row of red squares from afar.
    A patch is a run of cells of one strong colour (CIE chroma ROW_CHROMA+, the same 30-degree hue sector) in one row;
    ROW_PATCHES or more patches in one row of one side is a finding. Returns [{side, y, colour, patches, span}]."""
    if getattr(m, "rows", None) is not None:
        return m.rows
    house = {p: st for p, st in m.S.items() if (p[0], p[2]) in m.F2 and p[1] > m.g}
    cache, out = {}, []
    for side in ("north", "east", "south", "west"):
        rows = collections.defaultdict(list)
        for (a, b), (_near, p, st) in nearest(house, side).items():
            k = m.K.get(p)
            if k == "glass" or (k in ("stairs", "slab") and "half=top" not in st and "type=top" not in st):
                continue                                             # windows and roof slopes are not facade patches
            got = cache.get(st)
            if got is None:
                rgb = block_color(st)
                L_, A, B = lab(rgb)
                h = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])[0]
                got = cache[st] = (int(((h * 360 + 15) % 360) // 30) if (A * A + B * B) ** 0.5 >= ROW_CHROMA else None, rgb)
            if got[0] is not None:
                rows[(b, got[0])].append((a, got[1]))
        for (y, _hue), cells in sorted(rows.items()):
            xs = sorted(c[0] for c in cells)
            patches = 1 + sum(1 for u, v in zip(xs, xs[1:]) if v - u > 1)
            if patches >= ROW_PATCHES:
                out.append({"side": side, "y": y, "colour": _hue_name(cells[0][1]), "patches": patches,
                            "span": (xs[0], xs[-1]), "axis": "x" if side in ("north", "south") else "z"})
    m.rows = out
    return out


def _contrast(m):
    """Frame against fill, measured on the render (_view): the lightness gap between the log frame and the wall fill and
    the share of the wall the eye sees as light."""
    v = _view(m)
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    if v["wall_cells"] < 10:
        return 0, ["Wall contrast: almost no wall surface seen from outside."], [
            f"Build walls round x {x1}..{x2}, z {z1}..{z2}: a light fill (birch or oak planks) in an oak or spruce log "
            f"frame (pattern framed_house, style='light')."]
    dl, light = v["dl"], v["light"]
    c1 = _clamp((dl - 5) / 15)
    c3 = 1.0 if m.dark else _clamp((light - 0.2) / 0.4)
    score = 100 * c1 * (0.15 + 0.85 * c3)
    if c1 < 0.75:
        find.append(f"Wall contrast: the walls round x {x1}..{x2}, z {z1}..{z2} read as one tone on the render: frame "
                    f"lightness {round(v['frame_l'])}, fill {round(v['fill_l'])}, {round(dl)} apart (good: 20 or more).")
        fix.append(f"Fill the walls round x {x1}..{x2}, z {z1}..{z2} with a light material (birch or oak planks, stripped "
                   f"birch/oak logs, white terracotta) between oak or spruce log posts and beams: pattern "
                   f"framed_house(..., style='light').")
    if c3 < 0.75:
        find.append(f"Wall contrast: only {round(100 * light)}% of the wall seen from outside is light (lightness 45+); "
                    f"the reference houses show 60% or more light wood.")
        fix.append(f"Show more light wall round x {x1}..{x2}, z {z1}..{z2}: a light fill (birch or oak planks, stripped "
                   f"birch/oak logs) instead of spruce or dark oak, posts every 4-6 blocks, not every 2.")
    return score, find, fix


def _bright(v):
    """0..1: how far the walls are from reading dark (mean lightness 35 -> 0, 50 -> 1) and how much of them is light."""
    return min(_clamp((v["wall_l"] - 35) / 15), _clamp((v["light"] - 0.15) / 0.4))


def _looks(m):
    """The colours on the render against the reference houses: wall brightness, a coloured (not near-black or grey)
    roof, and how close the colour histogram of the house is to the nearest reference picture. A dark look asked for
    (dark_asked) is not penalised."""
    v = _view(m)
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    rows = _colour_rows(m)
    off = min(ROW_PENALTY[1], ROW_PENALTY[0] * len(rows))
    for r in rows[:3]:
        find.append(f"Looks: a row of {r['patches']} {r['colour']} patches along the {r['side']} side at y={r['y']} "
                    f"({r['axis']} {r['span'][0]}..{r['span'][1]}) reads as {r['colour']} squares from afar (one strong "
                    f"colour repeated, like the same flower under every window).")
    if rows:
        fix.append("Break the colour rows: soft mixed plants in the window planters (azure bluet, oxeye daisy, lily of "
                   "the valley, fern, azalea - window_with_box's default) and a planter under only every second window "
                   "of the lower floors (window_with_box(..., planter=False) gives the others a trapdoor sill).")
    hs = _clamp((v["closeness"] - LOOK_CLOSE[0]) / (LOOK_CLOSE[1] - LOOK_CLOSE[0])) if v["ref"] else 0.5
    if m.dark:
        return 100.0 - off, find, fix
    bright = _clamp((v["wall_l"] - 35) / 15)
    rc = v["roof_colour"] if v["roof_cells"] else 0.0
    score = 100 * (0.4 * bright + 0.25 * rc + 0.35 * hs) - off
    if bright < 0.75:
        find.append(f"Looks: the house reads dark on the render: mean wall lightness {round(v['wall_l'])} (the reference "
                    f"houses: 50 or more), {round(100 * v['light'])}% of the wall light.")
        fix.append(f"Lighten the walls round x {x1}..{x2}, z {z1}..{z2}: birch or oak planks or stripped birch/oak logs "
                   f"for the fill, oak or spruce logs for the frame; no dark oak, deepslate or blackstone walls unless "
                   f"the user asked for a dark build.")
    if v["roof_cells"] and rc < 0.6:
        find.append(f"Looks: the roof reads {'near-black' if v['roof_l'] < 30 else 'grey or dull'} (lightness "
                    f"{round(v['roof_l'])}); the reference roofs are teal or warm wood.")
        fix.append(f"Give the roof over x {x1}..{x2}, z {z1}..{z2} a colour: teal (prismarine_brick_stairs, "
                   f"stairs='teal'), green (oxidized_cut_copper_stairs) or warm oak, with an oak trim - "
                   f"gable_roof_trim(..., stairs='teal', trim='oak').")
    if hs < 0.6:
        find.append(f"Looks: the colour mix of the house is far from the reference houses (closeness "
                    f"{v['closeness']:.2f} to {v['ref'] or 'none'}; good: {LOOK_CLOSE[1]:.2f}+).")
        if not fix:
            fix.append("Use the reference palette: light oak/birch walls in an oak or spruce log frame, a teal roof with "
                       "an oak trim, white-framed windows; fewer grey and black blocks.")
    return score, find, fix


def is_small(size=None, prompt=None):
    """A small house by its size hint or prompt (tiny, small, hut, cottage ...): one storey is then fine."""
    text = f" {size or ''} {prompt or ''} ".lower().replace("-", " ")
    return any(f" {w}" in text for w in SMALL_WORDS)


def _levels(m, cols):
    """The storeys of a building: [(floor y, room cells, ceiling y)], low to high. A level counts as a storey when its
    rooms cover a fifth of the building and have walls (not roof slopes) round them at head height and a flat ceiling;
    the rooms under a pitched roof are an attic, not a storey."""
    bottoms = collections.defaultdict(list)
    for p in m.IN:
        if (p[0], p[2]) in cols and (p[0], p[1] - 1, p[2]) not in m.IN:
            bottoms[p[1]].append(p)
    need = max(MIN_ROOM_COLUMNS, 0.2 * len(cols))
    out = []
    for y in sorted(bottoms):
        good, ceils = [], []
        for comp in _components([(p[0], p[2]) for p in bottoms[y]]):
            if len(comp) < max(MIN_ROOM_COLUMNS, 0.1 * len(cols)):
                continue
            wall = roof = 0
            for (x, z) in comp:
                for d in DIRS4:
                    q = (x + d[0], y + 1, z + d[1])
                    if q in m.IN or q not in m.ST:
                        continue
                    if m.K[q] in ("stairs", "slab"):
                        roof += 1
                    else:
                        wall += 1
            tops = sorted(next(yy for yy in range(y, y + 64) if (x, yy + 1, z) not in m.IN) + 1 for (x, z) in comp)
            ceil = tops[len(tops) // 2]
            if roof > wall or sum(1 for t in tops if abs(t - ceil) <= 1) < 0.6 * len(tops):
                continue                                             # an attic under the roof slopes
            good += [(x, y, z) for (x, z) in comp]
            ceils += tops
        if len(good) < need:
            continue
        if out and y - out[-1][0] < 3:
            continue                                                 # a split level, not a new storey
        out.append((y, good, sorted(ceils)[len(ceils) // 2]))
    return out


def _storeys(m):
    parts, find, fix = [], [], []
    for b in _buildings(m) or [{"cols": m.F1, "rooms": list(m.I)}]:
        cols = set(b["rooms"])
        levels = _levels(m, cols)
        if not levels:
            continue
        g = min((m.cy[c][0] for c in b["cols"] if c in m.cy), default=m.g)
        floors = len(levels)
        tiny = m.small or len(cols) <= SMALL_ROOMS
        fl = 1.0 if floors >= 3 or (tiny and floors >= 1) else 0.8 if floors == 2 else 0.0
        xs = [c[0] for c in cols]
        zs = [c[1] for c in cols]
        tx = [p[0] for p in levels[-1][1]]                           # the main volume: the rooms of the top storey
        tz = [p[2] for p in levels[-1][1]]
        length = max(max(tx) - min(tx), max(tz) - min(tz)) + 3
        height = levels[-1][2] - g
        ratio = height / length
        rp = _clamp((ratio - 0.2) / 0.25)
        parts.append((len(cols), 100 * fl * (0.4 + 0.6 * rp)))
        where = f"x {min(xs) - 1}..{max(xs) + 1}, z {min(zs) - 1}..{max(zs) + 1}"
        if fl < 0.8:
            find.append(f"Storeys: the building at {where} has {floors} floor{'s' if floors != 1 else ''} (good houses: 2-3 "
                        f"floors unless it is a small hut or cottage).")
            fix.append(f"Raise the building at {where} to 2 floors (framed_house floors=2 with a storey band between the "
                       f"floors at y {levels[-1][2]}, pattern storey_band) and put the roof on top.")
        if rp < 0.6:
            find.append(f"Storeys: the building at {where} is long and low: {height} blocks to the top of the walls for "
                        f"{length} blocks of length (height/length {ratio:.2f}, good: 0.45 or more).")
            fix.append(f"Make the building at {where} taller and shorter: another floor on the main part, or split the "
                       f"{length}-block length into a taller main house and lower wings.")
    if not parts:
        return 0, ["Storeys: no floor with walls round it found."], [
            f"Give the building at x {m.box[0]}..{m.box[2]}, z {m.box[1]}..{m.box[3]} real walls and 2 floors."]
    area = sum(a for a, _ in parts)
    return sum(a * v for a, v in parts) / area, find[:4], fix[:4]


def _bad_window_cells(m):
    """Window openings that do not read as clear glass: a red (or other saturated red) stained pane, a flower or any
    plant right in front of a pane, or a red block filling a hole in a window (3 of its 4 in-wall neighbours are panes).
    Returns [(x, y, z, why)] sorted."""
    bad = {}
    red = lambda n: n.startswith("red_") or n in ("redstone_block", "poppy", "rose_bush", "red_tulip")   # noqa: E731
    for p, k in m.K.items():
        if k == "glass" and m.N[p].startswith("red_"):
            bad[p] = "red glass"
    for d, q, fk, mat, t, fr, box in _faces(m):
        if m.K.get(q) != "glass":
            continue
        o = (q[0] + d[0], q[1], q[2] + d[1])
        if m.K.get(o) == "nature":
            bad[o] = "a flower or plant in front of a pane"
    glass = {p for p, k in m.K.items() if k == "glass"}
    cand = set()
    for g in glass:
        for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (g[0] + a, g[1] + b, g[2] + c)
            if q in m.N and q not in glass:
                cand.add(q)
    for q in cand:
        for ax in ((1, 0), (0, 1)):                                  # the wall runs along x or along z
            n = sum(((q[0] + sx * ax[0], q[1], q[2] + sx * ax[1]) in glass) for sx in (1, -1))
            n += sum(((q[0], q[1] + sy, q[2]) in glass) for sy in (1, -1))
            if n >= 3 and (red(m.N[q]) or n == 4):
                bad[q] = "a non-glass block inside a window"
    return sorted((x, y, z, why) for (x, y, z), why in bad.items())


def _windows(m):
    side = collections.defaultdict(lambda: [0, 0])
    glass = {}
    for d, q, fk, mat, t, fr, box in _faces(m):
        if fk == "open":
            continue
        side[d][0] += 1
        if m.K.get(q) == "glass" and q not in glass:
            side[d][1] += 1
            glass[q] = d
    sides = {d: v for d, v in side.items() if v[0] >= 8}
    if not sides:
        return 0, [], []
    x1, z1, x2, z2 = m.box
    shares = {d: g / n for d, (n, g) in sides.items()}
    per = sum(_clamp(s / 0.15) for s in shares.values()) / max(4, len(shares))     # a side with no wall counts as blank
    big = 0
    left = set(glass)
    while left:
        start = left.pop()
        d = glass[start]
        ax, az = abs(d[1]), abs(d[0])                                # along the wall
        comp, todo = [start], [start]
        while todo:
            x, y, z = todo.pop()
            for q in ((x + ax, y, z + az), (x - ax, y, z - az), (x, y + 1, z), (x, y - 1, z)):
                if q in left and glass[q] == d:
                    left.remove(q)
                    comp.append(q)
                    todo.append(q)
        if len(comp) >= 4:
            big += len(comp)
    framed = 0
    for p in glass:
        near = [(p[0] + a, p[1] + b, p[2] + c) for a, b, c in
                ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                 (1, -1, 0), (-1, -1, 0), (0, -1, 1), (0, -1, -1))]
        if any(m.K.get(q) in ("trapdoor", "slab", "stairs", "frame", "fence", "nature", "pot") for q in near):
            framed += 1
    n = len(glass)
    score = 55 * per + 20 * (framed / n if n else 0) + 25 * (big / n if n else 0)
    find, fix = [], []
    holes = _bad_window_cells(m)
    if holes:
        score = max(0, score - min(60, 12 * len(holes)))
        find.append(f"Windows: {len(holes)} window opening(s) do not read as clear glass: "
                    + "; ".join(f"{w} at x {x}, y {y}, z {z}" for x, y, z, w in holes[:6]) + ".")
        fix.append("Windows are glass_pane (clear or white-tinted) in a white or birch or oak frame; put the flowers only "
                   "in a box directly under the window (pattern window_with_box), never in front of or inside the panes.")
    worst = min(shares, key=lambda d: shares[d])
    if shares[worst] < 0.12 or len(shares) < 4:
        find.append("Windows: glass on each facade: " + ", ".join(f"{SIDE[d]} {round(100 * shares[d])}%" for d in sorted(
            shares, key=lambda d: SIDE[d])) + " (good: 12-20% of every facade).")
        wx = {(0, -1): f"z {z1 - 1}", (0, 1): f"z {z2 + 1}", (1, 0): f"x {x2 + 1}", (-1, 0): f"x {x1 - 1}"}[worst]
        fix.append(f"Put big windows on the {SIDE[worst]} wall ({wx}): 2 x 2 panes in every bay between the posts, with "
                   f"shutters and a flower box (window_with_box(..., width=2, height=2)).")
    if n and big / n < 0.5:
        find.append(f"Windows: {n - big} of {n} panes are in small windows (fewer than 4 panes together).")
        fix.append(f"Make the windows round x {x1}..{x2}, z {z1}..{z2} 2 wide and 2 high (window_with_box width=2, "
                   f"height=2), framed with shutters, a log lintel and a flower box.")
    return score, find, fix


def _balcony(m):
    zone = _dilate(m.F1, 4)
    low = m.g + 3
    free = ("air", "soft", "light")

    def open_above(p, h):
        q = (p[0], p[1] + h, p[2])
        return q not in m.N or m.K[q] in free

    floor = {}
    for p, k in m.K.items():
        if k not in ("full", "frame", "slab") or p[1] < low or (p[0], p[2]) not in zone:
            continue
        if (p[0], p[1] + 1, p[2]) in m.IN or p in m.chimneys:
            continue
        up = (p[0], p[1] + 1, p[2])
        rail = up in m.K and m.K[up] in ("fence", "frame")
        if open_above(p, 2) and (rail or open_above(p, 1)):
            floor[p] = rail
    groups = []
    left = set(floor)
    while left:
        s = left.pop()
        comp, todo = [s], [s]
        while todo:
            x, y, z = todo.pop()
            for a, b in DIRS4:
                q = (x + a, y, z + b)
                if q in left:
                    left.remove(q)
                    comp.append(q)
                    todo.append(q)
        walk = [p for p in comp if not floor[p]]
        rails = sum(1 for p in comp if floor[p]) + sum(
            1 for (x, y, z) in walk for a, b in DIRS4 if m.K.get((x + a, y + 1, z + b)) == "fence")
        if len(walk) >= 3 and rails >= 3:
            groups.append(comp)
    cells = sum(len(c) for c in groups)
    stair = _outside_stair(m)
    score = 35 * bool(groups) + 25 * (len(groups) >= 2) + 25 * _clamp(cells / 24) + 15 * bool(stair)
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    if not groups:
        find.append(f"Balconies: no balcony or terrace (an outdoor floor above the ground floor with a railing) on the "
                    f"building at x {x1}..{x2}, z {z1}..{z2}.")
        fix.append(f"Add a balcony on the upper floor of the front wall (pattern balcony with door=True, floor at y "
                   f"{m.g + 5}) and a terrace with a fence railing on a lower wing, reached by an outside stair "
                   f"(pattern external_stair).")
    elif len(groups) < 2:
        p = min(groups[0])
        find.append(f"Balconies: one balcony or terrace ({len(groups[0])} cells at {_fmt(p)}); the reference houses "
                    f"have two or more.")
        fix.append(f"Add a second balcony or a roof terrace with a railing on another side of x {x1}..{x2}, "
                   f"z {z1}..{z2} (patterns balcony, external_stair).")
    if groups and not stair:
        fix.append("Lead an outside stair with landings up to the terrace or balcony (pattern external_stair).")
    return score, find, fix


def _outside_stair(m):
    """A flight of 3+ bottom stairs outside the rooms climbing from near the ground to an upper floor or terrace
    (flat landings of up to 3 cells between the flights are fine)."""
    for p, k in m.K.items():
        if k != "stairs" or p[1] > m.g + 2 or (p[0], p[2]) in m.I or "half=top" in m.S[p]:
            continue
        facing = _props(m.S[p]).get("facing")
        f = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}.get(facing)
        if not f:
            continue
        x, y, z = p
        steps = 1
        while steps < 60:
            q = (x + f[0], y + 1, z + f[1])
            k2 = 0
            while m.K.get(q) != "stairs" and k2 < 3 and (q[0], q[1] - 1, q[2]) in m.ST:
                q = (q[0] + f[0], q[1], q[2] + f[1])                 # walk over a landing
                k2 += 1
            if m.K.get(q) != "stairs" or "half=top" in m.S[q] or _props(m.S[q]).get("facing") != facing:
                break
            x, y, z = q
            steps += 1
        if steps >= 4 and y >= m.g + 4:
            return p
    return None


def _roof_planes(m):
    """Roof planes: bottom stairs open to the sky over and round the building, grouped by facing -> [(eave y, cells)]."""
    zone = _dilate(m.F1, 3)
    by = collections.defaultdict(set)
    for p, k in m.K.items():
        if k != "stairs" or (p[0], p[2]) not in zone or p[1] < m.g + 3 or "half=top" in m.S[p]:
            continue
        if m.K.get((p[0], p[1] + 1, p[2])) in ("full", "frame", "stairs", "slab"):
            continue                                                 # covered: under another roof or a wall
        by[_props(m.S[p]).get("facing", "?")].add(p)
    out = []
    for facing, cells in by.items():
        left = set(cells)
        while left:
            s = left.pop()
            comp, todo = [s], [s]
            while todo:
                x, y, z = todo.pop()
                for a, b in DIRS4:
                    for dy in (-1, 0, 1):
                        q = (x + a, y + dy, z + b)
                        if q in left:
                            left.remove(q)
                            comp.append(q)
                            todo.append(q)
            if len(comp) >= 6:
                out.append((min(q[1] for q in comp), comp))
    return out


def _roof_style(m):
    roof = collections.Counter()
    for c in m.F1:
        p = m.top_state(c)
        if p is not None and p not in m.chimneys and m.K[p] in ("stairs", "slab", "full") and p[1] >= m.g + 3:
            roof[mkey(m.N[p])] += 1
    vis = _seen(m)
    walls = [mat for mat, n in vis.most_common(3) if n >= 0.1 * max(1, sum(vis.values()))]
    x1, z1, x2, z2 = m.box
    find, fix = [], []
    rm = roof.most_common(1)[0][0] if roof else None
    near, col = None, 0.0
    if rm and walls:
        near = min(walls, key=lambda w: _cdist(rm, w))
        col = 0.5 * _clamp(_cdist(rm, near) / 50) + 0.5 * min(_hue_gap(rm, w) for w in walls)
        if not m.dark:
            col *= 0.3 + 0.7 * _view(m)["roof_colour"]               # a near-black or grey roof is no colour of its own
    levels = []
    for y, comp in sorted(_roof_planes(m)):
        if not levels or y - levels[-1] >= 2:
            levels.append(y)
    lay = 0.0 if len(levels) <= 1 else 0.6 if len(levels) == 2 else 1.0
    score = 60 * col + 40 * lay
    if col < 0.75:
        find.append(f"Roof colour: the roof over x {x1}..{x2}, z {z1}..{z2} ({rm or 'none'}) is the same colour family as "
                    f"the walls ({near or ', '.join(walls) or 'none'}).")
        fix.append(f"Give the roof over x {x1}..{x2}, z {z1}..{z2} its own colour: teal (prismarine_brick_stairs), green "
                   f"(oxidized_cut_copper_stairs), red (red_nether_brick_stairs) or brick with an oak trim - "
                   f"gable_roof_trim(..., stairs='teal', trim='oak'); grey or near-black only for a dark build.")
    if lay < 1:
        find.append(f"Roof layers: roof planes at {len(levels)} height{'s' if len(levels) != 1 else ''} "
                    f"({', '.join(f'y {y}' for y in levels) or 'none'}); the reference houses layer 3 or more.")
        fix.append(f"Layer the roofs: a storey band (pattern storey_band) round x {x1}..{x2}, z {z1}..{z2} between the "
                   f"floors, lower wing and porch roofs below the main eaves, a cross gable (pattern cross_gable_roof).")
    return score, find, fix


# ------------------------------------------------------------------ shape (round 4: massing on the render)
SHAPE_RUN = (9, 18)                  # straight wall run: full points up to 9 blocks, none from 18
SHAPE_RIDGE = (12, 24)               # the longest flat ridge seen from a side: full up to 12 blocks, none from 24
SMALL_FILL = 0.3                     # a small house shows a pale fill (birch, stripped birch, plaster) on 30%+ of its wall
SHAPE_SMALL = 100                    # a house with this many room columns or fewer needs no wings (a cottage)
SHAPE_CAP = (30, 70)                 # a big house with no shape (one long box, one ridge) scores at most 30 + 70 x shape
SIL_KINDS = ("full", "frame", "stairs", "slab", "glass")
SIDE_OF = {(0, 1): "south", (0, -1): "north", (1, 0): "east", (-1, 0): "west"}
OPP_SIDE = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _profile_peaks(prof, ground):
    """Peaks of one silhouette (a list of top heights, left to right): [(height, start, end, prominence)] for every
    plateau higher than both neighbours, its prominence the drop to the higher of the two valleys round it (the ground
    past the ends)."""
    runs = []
    for i, h in enumerate(prof):
        if runs and runs[-1][0] == h:
            runs[-1][2] = i
        else:
            runs.append([h, i, i])
    out = []
    for j, (h, a, b) in enumerate(runs):
        lh = runs[j - 1][0] if j else ground
        rh = runs[j + 1][0] if j + 1 < len(runs) else ground
        if h <= lh or h <= rh:
            continue
        lows = []
        for step in (-1, 1):                                         # of two equal peaks the right one keeps the drop
            k, low = j + step, h
            while 0 <= k < len(runs) and (runs[k][0] <= h if step < 0 else runs[k][0] < h):
                low = min(low, runs[k][0])
                k += step
            lows.append(ground if not 0 <= k < len(runs) else low)
        while a > 0 and prof[a - 1] >= h - 1:                        # the ridge: the top within 1 block (finials,
            a -= 1                                                   # a cross gable 1 higher are the same ridge)
        while b + 1 < len(prof) and prof[b + 1] >= h - 1:
            b += 1
        out.append((h, a, b, h - max(lows)))
    return out


def _despike(prof):
    """The outline without spikes: a top 1-2 columns wide standing 2+ blocks over both neighbours (a finial, a post, a
    flag pole, a chimney the chimney test missed) is cut down to the higher neighbour. A gable seen end-on steps down
    1 at a time, so it stays."""
    prof = list(prof)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(prof):
            j = i
            while j + 1 < len(prof) and prof[j + 1] == prof[i]:
                j += 1
            if j - i <= 1:
                lh = prof[i - 1] if i else None
                rh = prof[j + 1] if j + 1 < len(prof) else None
                nb = [v for v in (lh, rh) if v is not None]
                if nb and all(prof[i] - v >= 2 for v in nb) and len(nb) == 2:
                    for k in range(i, j + 1):
                        prof[k] = max(nb)
                    changed = True
            i = j + 1
    return prof


def _lower_tops(prof, H, ground):
    """The wing tops of an outline: [(height, column)] of every local top (a gable or a flat ridge, higher than the
    columns next to it on both sides or on one side and level on the other) at least 4 over the ground and 2+ under H."""
    out = []
    for i, h in enumerate(prof):
        if h < ground + 4 or h > H - 2:
            continue
        lh = prof[i - 1] if i else ground
        rh = prof[i + 1] if i + 1 < len(prof) else ground
        if h >= lh and h >= rh and (h > lh or h > rh):
            out.append((h, i))
    return out


def _sloped(prof, a, b):
    """A pitched peak: the outline steps down 1 block at a time for 2+ steps on a side of the ridge a..b."""
    for i, step in ((a, -1), (b, 1)):
        n, k = 0, i
        while 0 <= k + step < len(prof) and prof[k] - prof[k + step] == 1:
            n += 1
            k += step
        if n >= 2:
            return True
    return False


def _house_cells(m):
    """The house as the render shows it for the outline: structural blocks on the building's columns and 2 round
    them above the foundation; chimneys, lights, fences and props left out."""
    chim = {(q[0], q[2]) for q in m.chimneys}
    return {p: m.S[p] for p in m.ST if (p[0], p[2]) in m.F2 and (p[0], p[2]) not in chim and p[1] > m.g
            and m.K[p] in SIL_KINDS}


def _silhouettes(m):
    """The outline of the house against the sky from each side, on the render (render.nearest of _house_cells):
    {side: {"top": [heights left to right as the viewer sees it], "across": [the view column of each], "peaks":
    [(height, start, end, prominence)] with prominence 2+, "ridge": the longest flat peak in blocks, "levels": the roof
    heights seen (peaks and flat runs of 3+ columns at 4+ over the ground, 2+ apart), "width": columns}}."""
    if getattr(m, "sil", None) is not None:
        return m.sil
    house = _house_cells(m)
    out = {}
    for side in ("north", "east", "south", "west"):
        view = nearest(house, side)
        tops = {}
        for (a, v) in view:
            if v > tops.get(a, -10 ** 9):
                tops[a] = v
        if not tops:
            continue
        across = list(range(min(tops), max(tops) + 1))
        if side in ("north", "east"):                                # left to right as the viewer sees it
            across = across[::-1]
        prof = _despike([tops.get(a, m.g) for a in across])
        peaks = [p for p in _profile_peaks(prof, m.g) if p[3] >= 2]
        ridge = max((b - a + 1 for h, a, b, pr in peaks), default=0)
        hs = {h for h, a, b, pr in peaks}
        i = 0
        while i < len(prof):                                         # flat runs: a wing ridge, a shoulder, a terrace roof
            j = i
            while j + 1 < len(prof) and prof[j + 1] == prof[i]:
                j += 1
            if j - i >= 2 and prof[i] >= m.g + 4:
                hs.add(prof[i])
            i = j + 1
        levels = []
        for h in sorted(hs):
            if not levels or h - levels[-1] >= 2:
                levels.append(h)
        out[side] = {"top": prof, "across": across, "peaks": peaks, "ridge": ridge, "levels": levels,
                     "width": len(prof), "view": view}
    m.sil = out
    return out


def _wall_runs(m):
    """The straight runs of the outside walls (the outline of the rooms, seen from each side): [(blocks, side, (x, z) of
    the first wall cell, (x, z) of the last)], longest first. A step of the wall line in or out (a wing, a bay, a
    set-back) ends a run; log posts in the wall and inner walls meeting it (rooms side by side) do not. Inner walls
    between two rooms are not outside walls."""
    if getattr(m, "runs", None) is not None:
        return m.runs
    high = collections.Counter((p[0], p[2]) for p in m.IN)
    cols = {c for c in m.I if high[c] >= 3}                         # not the 2-high crawl space under a deck on stilts
    cols = cols if cols else set(m.I)
    edges = collections.defaultdict(list)
    for (x, z) in cols:
        for d in DIRS4:
            if any((x + d[0] * k, z + d[1] * k) in cols for k in range(1, 5)):
                continue
            if d[0]:
                edges[(d, x)].append(z)
            else:
                edges[(d, z)].append(x)
    runs = []
    for (d, plane), along in edges.items():
        along.sort()
        start = prev = along[0]
        w = plane + (d[0] or d[1])                                   # the wall line
        for v in along[1:] + [None]:
            if v is not None and (v == prev + 1 or (v - prev <= 4 and all(
                    q in m.cy and q not in cols for q in (((w, g) if d[0] else (g, w)) for g in range(prev + 1, v))))):
                prev = v                                             # the same wall goes on past an inner wall
                continue
            n = prev - start + 3                                     # the wall cells: the room's edge and both corners
            a, b = ((w, start - 1), (w, prev + 1)) if d[0] else ((start - 1, w), (prev + 1, w))
            runs.append((n, SIDE_OF[d], a, b))
            if v is not None:
                start = prev = v
    runs.sort(reverse=True)
    m.runs = runs
    return runs


def _entrance(m):
    """The side of the main door: the lowest outside doors, the side most of them face. None without a door."""
    doors = _doors(m)
    if not doors:
        return None
    low = min(p[1] for p, d in doors)
    cnt = collections.Counter(SIDE_OF[d] for p, d in doors if p[1] <= low + 1)
    return cnt.most_common(1)[0][0]


def _front_feature(m, side):
    """What the entrance side shows: a gable end facing that way (a sharp peak of the outline with the gable fill, not
    roof stairs, under its top), a porch (posts and a roof 2-8 blocks in front of the wall line) and a stair or steps
    (3+ bottom stairs there). Returns (gable, porch, stair)."""
    s = _silhouettes(m).get(side)
    gable = False
    if s:
        for h, a, b, pr in s["peaks"]:
            if pr < 3 or b - a > 3:
                continue
            col = s["across"][(a + b) // 2]
            below = [s["view"].get((col, h - k)) for k in (2, 3, 4)]
            if sum(1 for c in below if c and m.K[c[1]] in ("full", "frame")) >= 2:
                gable = True
                break
    d = {v: k for k, v in SIDE_OF.items()}[side]
    sign = d[0] or d[1]
    front = {}
    for (x, z) in m.I:
        key, out = (z, x) if d[0] else (x, z)
        if key not in front or out * sign > front[key] * sign:
            front[key] = out
    posts = roofs = steps = 0
    for p, k in m.K.items():
        x, y, z = p
        key, out = (z, x) if d[0] else (x, z)
        dist = (out - front[key]) * sign if key in front else 0   # 1 = the wall, 2 = its frame, 2-3 = the eaves
        if not 2 <= dist <= 9 or y < m.g - 1:
            continue
        if k == "frame" and y >= m.g + 1 and dist >= 3:
            posts += 1
        elif k in ("stairs", "slab") and y >= m.g + 3 and dist >= 4:
            roofs += 1
        elif k == "stairs" and "half=top" not in m.S[p]:
            steps += 1
    return gable, posts >= 3 and roofs >= 5, steps >= 3


def _shape(m):
    """Massing and silhouette, on the render: several gables and roof heights seen from every side (no long single
    ridge), a taller central block with lower wings either side in the entrance view, no straight wall run over 9
    blocks, a gable, porch or stair on the entrance side. A small house (one storey is fine) needs no wings."""
    sil = _silhouettes(m)
    if not sil:
        return 0, [], []
    runs = _wall_runs(m)
    x1, z1, x2, z2 = m.box
    small = m.small or len(m.I) <= SHAPE_SMALL
    find, fix = [], []
    # 1. silhouette variety: roof heights and gables from each side (3 gables on the entrance side and its back), the
    #    longest flat ridge seen from any side
    ent = _entrance(m) or max(sil, key=lambda k: sil[k]["width"])
    var = []
    for side, s in sil.items():
        need = 1 if small or side not in (ent, OPP_SIDE[ent]) else 3
        var.append(0.6 * (1.0 if small else _clamp((len(s["levels"]) - 1) / 2)) + 0.4 * _clamp(len(s["peaks"]) / need))
    longest = max(sil.items(), key=lambda kv: kv[1]["ridge"])
    rr = _clamp((SHAPE_RIDGE[1] - longest[1]["ridge"]) / (SHAPE_RIDGE[1] - SHAPE_RIDGE[0]))
    pitched = any(_sloped(s["top"], a, b) for s in sil.values() for h, a, b, pr in s["peaks"])
    sil_v = (0.6 * sum(var) / len(var) + 0.4 * rr) * (1.0 if pitched else 0.4)      # a flat top is no gable at all
    # 2. height spread: the roof heights over all sides, tallest against lowest
    levels = []
    for h in sorted({h for s in sil.values() for h in s["levels"]}):
        if not levels or h - levels[-1] >= 2:
            levels.append(h)
    spread = (levels[-1] - levels[0]) if levels else 0
    spr = 1.0 if small else 0.5 * _clamp((len(levels) - 1) / 2) + 0.5 * _clamp(spread / 5)
    # 3. the longest straight wall run, and the share of the wall in runs over 9
    top_run = runs[0] if runs else (0, "", (0, 0), (0, 0))
    total = sum(r[0] for r in runs) or 1
    over = sum(r[0] for r in runs if r[0] > SHAPE_RUN[0]) / total
    wr = 0.6 * _clamp((SHAPE_RUN[1] - top_run[0]) / (SHAPE_RUN[1] - SHAPE_RUN[0])) + 0.4 * (1 - over)
    # 4. a front feature on the entrance side
    gable, porch, stair = _front_feature(m, ent)
    fr = 0.45 * gable + 0.3 * porch + 0.25 * stair
    if small:
        fr = min(1.0, 0.5 * gable + 0.6 * porch + 0.4 * stair)      # a cottage: a porch or a gable over the door
    # 5. hierarchy: the tallest peak in the middle of the entrance view, lower wings with peaks on both sides
    hier, cen, wings = (1.0 if small else 0.0), False, 0
    s = sil.get(ent)
    if s and s["peaks"]:
        H, a, b, pr = max(s["peaks"], key=lambda p: (p[0], -abs((p[1] + p[2]) / 2 - s["width"] / 2)))
        cen = 0.3 <= (a + b) / 2 / max(1, s["width"] - 1) <= 0.7 and b - a + 1 <= 0.5 * s["width"]
        lows = _lower_tops(s["top"], H, m.g)
        left = [h for h, i in lows if i < a]
        right = [h for h, i in lows if i > b]
        wings = bool(left) + bool(right)
        sym = (1.0 if abs(max(left) - max(right)) <= 2 else 0.5) if left and right else 0.0
        if not small:
            hier = 0.35 * cen + 0.2 * bool(left) + 0.2 * bool(right) + 0.25 * sym
    if small:                                                        # no wings asked of a cottage: outline, walls, front
        score = 100 * (0.3 * sil_v + 0.25 * wr + 0.45 * fr)
    else:
        score = 100 * (0.25 * sil_v + 0.2 * spr + 0.25 * wr + 0.15 * fr + 0.15 * hier)
    # a small house still needs some massing: a porch, lean-to or dormer, a chimney, 2 storeys or a loft, a pale fill
    levels_ = _levels(m, set(m.I))
    ceil = levels_[0][2] if levels_ else m.g
    loft = len({(p[0], p[2]) for p in m.IN if p[1] > ceil}) >= 0.3 * len(m.I)
    v = _view(m)
    needs = {"a porch, lean-to or dormer": porch or len(levels) >= 2 or any(len(t["peaks"]) >= 2 for t in sil.values()),
             "a chimney": bool(m.chimneys), "2 storeys or a loft": len(levels_) >= 2 or loft,
             "a pale wall fill": m.dark or v["fill_share"] >= SMALL_FILL}
    m.shape = {"score": round(score), "small_missing": [k for k, ok in needs.items() if not ok], "silhouette": round(sil_v, 2), "peaks": {k: len(v["peaks"]) for k, v in sil.items()},
               "longest_ridge": longest[1]["ridge"], "roof_heights": len(levels), "height_spread": spread,
               "longest_wall": top_run[0], "wall_over_9": round(over, 2), "entrance": ent, "front_gable": gable,
               "porch": porch, "front_stair": stair, "central_block": cen, "wings": wings, "small": small}
    if sil_v < 0.75:
        find.append(f"Shape: the outline is plain: a flat ridge of {longest[1]['ridge']} blocks seen from the "
                    f"{longest[0]}; " + ", ".join(f"{len(v['peaks'])} gable or peak{'s' if len(v['peaks']) != 1 else ''}"
                                                  f" from the {k}" for k, v in sil.items())
                    + " (the reference manors: 3+ gables at several heights from every side, no ridge over 12).")
        fix.append(f"Break the roof over x {x1}..{x2}, z {z1}..{z2} into several gables: a taller central block with a "
                   f"big front gable and lower wings with their own gables (pattern manor_layout), cross gables or "
                   f"dormers on long roofs (patterns cross_gable_roof, dormer).")
    if not small and spr < 0.75:
        find.append(f"Shape: roof peaks at {', '.join(f'y {h}' for h in levels) or 'no height'} ({spread} blocks from "
                    f"the lowest to the tallest; the references: 3 heights, 5+ apart).")
        fix.append(f"Make the central block one storey taller than the wings round x {x1}..{x2}, z {z1}..{z2} and give "
                   f"each wing a lower ridge (pattern manor_layout: 3 storeys in the middle, 2 in the wings).")
    if wr < 0.75 and runs:
        n, side, a, b = top_run
        find.append(f"Shape: a straight {side} wall of {n} blocks from x {a[0]}, z {a[1]} to x {b[0]}, z {b[1]} with no "
                    f"step, bay or wing (good: 9 or less).")
        fix.append(f"Step the {side} wall between x {a[0]}, z {a[1]} and x {b[0]}, z {b[1]}: set a wing back 2-3 blocks "
                   f"or push a bay or the central block out 2 (patterns bay_window, manor_layout).")
    if fr < 0.75:
        miss = [w for w, ok in (("front gable", gable), ("porch", porch), ("front stair", stair)) if not ok]
        find.append(f"Shape: the entrance ({ent}) side has no {', no '.join(miss)}.")
        fix.append(f"Give the {ent} side a big gable over the door, a porch with posts and a grand stair with landings "
                   f"up to it (patterns manor_layout, porch, external_stair).")
    if not small and hier < 0.75:
        find.append(f"Shape: no clear central block with wings on the {ent} side (tallest roof in the middle: "
                    f"{'yes' if cen else 'no'}; lower wings beside it: {wings} of 2).")
        fix.append(f"Build a central block one storey taller than two stepped wings, one each side of the entrance "
                   f"(pattern manor_layout).")
    return score, find, fix


PARTS = (("contrast", _contrast), ("looks", _looks), ("storeys", _storeys), ("windows", _windows), ("balcony", _balcony),
         ("roof_style", _roof_style), ("facade", _facade), ("roof", _roof), ("massing", _massing), ("palette", _palette),
         ("detail", _detail), ("surroundings", _surroundings), ("shape", _shape))


# ------------------------------------------------------------------ towns (3+ buildings)
def _buildings(m):
    """The separate buildings: groups of rooms whose walls touch (a house and its wing are one building)."""
    out = []
    for comp in _components(m.F1):
        rooms = [c for c in comp if c in m.I]
        if len(rooms) >= MIN_ROOM_COLUMNS:
            out.append({"cols": set(comp), "rooms": rooms})
    for b in out:
        g = min((m.cy[c][0] for c in b["cols"] if c in m.cy), default=m.g)
        b["area"] = len(b["cols"])
        b["height"] = max((m.T[c] for c in b["cols"] if c in m.T), default=g) - g
        facing = collections.Counter()
        for c in b["cols"]:
            p = m.top_state(c)
            if p is not None and m.K[p] == "stairs":
                facing[_props(m.S[p]).get("facing")] += 1
        ns, ew = facing["north"] + facing["south"], facing["east"] + facing["west"]
        b["ridge"] = None if not (ns or ew) else "x" if ns >= ew else "z"
    return out


def _cv(vals):
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5 / mean if mean else 0.0


def _roads(m, houses):
    road = set()
    for p, n in m.N.items():
        c = (p[0], p[2])
        if c in houses or (p[0], p[1] + 1, p[2]) in m.ST:
            continue
        if (n in PATH_BLOCKS or n in ("dirt_path", "gravel", "packed_mud", "mud_bricks", "bricks", "smooth_stone")
                or (m.K[p] in ("stairs", "slab") and "half=top" not in m.S[p] and "type=top" not in m.S[p])):
            road.add(c)
    return road


def _town(m, bs):
    """Town parts, each 0-100: roads (winding, reaching the doors), variety, open space, landmark, density."""
    zone = set()
    for b in bs:
        zone |= b["cols"]
    houses = _dilate(zone, 2)
    road = _roads(m, houses)
    near = _dilate(zone, 1)
    x1, x2 = min(c[0] for c in near), max(c[0] for c in near)
    z1, z2 = min(c[1] for c in near), max(c[1] for c in near)
    area = f"x {x1}..{x2}, z {z1}..{z2}"
    parts, find, fix = {}, [], {k: [] for k in TOWN_WEIGHTS}
    # streets: they reach every door and bend or branch instead of one straight line
    doors = _doors(m)
    reached = 0
    for b in bs:
        ds = [p for p, d in doors if (p[0], p[2]) in b["cols"]]
        if any((p[0] + a, p[2] + c) in road for p in ds for a in range(-8, 9) for c in range(-8, 9)):
            reached += 1
    straight = 0.0
    if len(road) >= 10:
        for axis in (0, 1):
            cnt = collections.Counter(c[1 - axis] for c in road)
            best = max(sum(cnt.get(v + k, 0) for k in range(5)) for v in cnt)
            straight = max(straight, best / len(road))
        winding = 1 - straight
        parts["roads"] = 40 * reached / len(bs) + 60 * min(1, winding / 0.4)
        if winding < 0.4:
            find.append(f"Town: {round(100 * straight)}% of the streets are one straight line.")
            fix["roads"].append(f"Let the streets bend, branch and follow the contours in {area}: a curve, a side lane "
                                f"(pattern road with several points, or the street lines of plan_layout).")
        if reached < len(bs):
            find.append(f"Town: {len(bs) - reached} of {len(bs)} buildings have no street within 8 blocks of a door.")
            fix["roads"].append("Run a path from every front door to the street.")
    else:
        parts["roads"] = 0
        find.append(f"Town: no streets between the {len(bs)} buildings ({area}).")
        fix["roads"].append(f"Lay streets that follow the ground between the buildings in {area} (plan_layout gives "
                            f"the street lines; pattern road draws a winding path through points).")
    # variety: sizes, heights, which way the ridges run
    areas = [b["area"] for b in bs]
    heights = [b["height"] for b in bs]
    ridges = collections.Counter(b["ridge"] for b in bs if b["ridge"])
    turn = min(ridges.get("x", 0), ridges.get("z", 0)) / len(bs)
    parts["variety"] = 35 * min(1, _cv(areas) / 0.3) + 35 * min(1, turn / 0.25) + 30 * min(1, _cv(heights) / 0.15)
    if parts["variety"] < 60:
        find.append(f"Town: the buildings are alike (sizes {sorted(areas)}, heights {sorted(heights)}, "
                    f"ridges {dict(ridges) or 'none'}).")
        fix["variety"].append("Vary the houses: different sizes and storeys, turn some so their ridge runs the other "
                              "way, different porches and roofs (framed_house, gable_roof_trim ridge 'x' or 'z').")
    # open space between the houses
    kinds = set()
    for p, n in m.N.items():
        c = (p[0], p[2])
        if c in houses or not (x1 <= c[0] <= x2 and z1 <= c[1] <= z2):
            continue
        k = m.K[p]
        if k == "fence":
            kinds.add("fence")
        elif k == "farm" or n in ("hay_block", "composter"):
            kinds.add("farm")
        elif n in FLOWERS or _leaf(n) or n.endswith("_sapling"):
            kinds.add("plants")
        elif n == "water":
            kinds.add("water")
        elif k == "light":
            kinds.add("light")
    if any(all((c[0] + a, c[1] + b) in road for a in range(5) for b in range(5)) for c in road):
        kinds.add("plaza")
    parts["open_space"] = 20 * min(5, len(kinds))
    if len(kinds) < 4:
        find.append(f"Town: little between the houses ({', '.join(sorted(kinds)) or 'nothing'}).")
        fix["open_space"].append(f"Add a paved plaza (5 x 5 or more), trees, fenced gardens, lantern posts and a well "
                                 f"or pond between the houses in {area}.")
    # a landmark: one building clearly bigger or taller
    med_a = sorted(areas)[len(areas) // 2]
    med_h = sorted(heights)[len(heights) // 2]
    landmark = max(areas) >= 1.8 * med_a or max(heights) >= med_h + 5
    parts["landmark"] = 100 if landmark else 0
    if not landmark:
        find.append("Town: no landmark - no building is clearly bigger or taller than the rest.")
        fix["landmark"].append(f"Make one building a landmark near the middle of {area}: twice the size or 5+ blocks "
                               f"taller (a hall, temple, tower or manor).")
    # density: how much of the town area the buildings cover
    d = sum(areas) / ((x2 - x1 + 7) * (z2 - z1 + 7))
    dens = 1.0 if 0.12 <= d <= 0.45 else max(0.0, (d - 0.03) / 0.09) if d < 0.12 else max(0.0, (0.7 - d) / 0.25)
    parts["density"] = 100 * dens
    if dens < 0.7:
        tight = d > 0.45
        find.append(f"Town: the buildings cover {round(100 * d)}% of the town area, "
                    f"{'packed too tight' if tight else 'spread too thin'} (good: 12-45%).")
        fix["density"].append("Spread the houses out with gardens and lanes between them." if tight else
                              "Bring the houses closer together along the streets, or add more buildings.")
    return {k: int(round(max(0, min(100, v)))) for k, v in parts.items()}, find, fix


TOWN_WEIGHTS = {"roads": 25, "variety": 25, "open_space": 20, "landmark": 15, "density": 15}
LABELS.update({"roads": "Streets", "variety": "Variety", "open_space": "Open space", "landmark": "Landmark",
               "density": "Density"})
LABELS["shape"] = "Shape (massing and outline)"


def score(blocks, size=None, prompt=None):
    """Quality of a building, see the module text. `size` (the size hint) and `prompt` (what was asked) only tell a
    small house (tiny, small, hut, cottage ...), which may have one storey. Three or more separate buildings are a town:
    the total is half the house parts, half the town parts (TOWN_WEIGHTS: winding streets that reach the doors, varied
    houses, open space, a landmark, density)."""
    m = _Model(blocks or {})
    m.small = is_small(size, prompt)
    m.dark = dark_asked(prompt, size)
    if not m.building:
        return {"total": None, "building": False, "town": False, "buildings": 0, "parts": {}, "fixes": {}, "weights": {},
                "findings": ["Not a building (no closed room with 2 blocks of head room), so its quality is not scored."]}
    parts, findings, fixes = {}, [], {}
    for key, fn in PARTS:
        val, find, fix = fn(m)
        parts[key] = int(round(max(0, min(100, val))))
        findings += find
        fixes[key] = fix
    weights = dict(WEIGHTS)
    bs = _buildings(m)
    town = len(bs) >= 3
    if town:
        tparts, tfind, tfix = _town(m, bs)
        parts.update(tparts)
        findings = tfind + findings
        fixes.update(tfix)
        weights = {k: v / 2 for k, v in WEIGHTS.items()}
        weights.update({k: v / 2 for k, v in TOWN_WEIGHTS.items()})
    total = int(round(sum(parts[k] * w for k, w in weights.items()) / sum(weights.values())))
    v = _view(m)
    looks = {"wall_lightness": round(v["wall_l"], 1), "light_share": round(v["light"], 2), "frame_lightness":
             round(v["frame_l"], 1), "fill_lightness": round(v["fill_l"], 1), "roof_lightness": round(v["roof_l"], 1),
             "roof_colour": round(v["roof_colour"], 2), "closeness": round(v["closeness"], 2), "nearest_ref": v["ref"],
             "dark_asked": m.dark, "cap": None}
    sh = getattr(m, "shape", None)
    looks["shape_cap"] = None
    if sh and not town and not sh["small"]:
        cap = int(round(SHAPE_CAP[0] + SHAPE_CAP[1] * sh["score"] / 100))
        if cap < total:
            looks["shape_cap"] = cap
            findings.insert(0, f"Shape: a big house that reads as one long box (shape {sh['score']}/100: longest wall "
                               f"{sh['longest_wall']}, longest ridge {sh['longest_ridge']}, {sh['roof_heights']} roof "
                               f"height{'s' if sh['roof_heights'] != 1 else ''}), so the total is held at {cap} (it would "
                               f"be {total}). A taller central block with a front gable and stepped wings lifts it "
                               f"(pattern manor_layout).")
            total = cap
    if sh and not town and sh["small"] and sh["small_missing"]:
        k = len(sh["small_missing"])
        cap = QUALITY_MIN - 1 - 8 * (k - 1)
        if cap < total:
            looks["shape_cap"] = cap
            findings.insert(0, f"Shape: a small house that is a plain box: it has no {', no '.join(sh['small_missing'])}, "
                               f"so the total is held at {cap} (it would be {total}). Add a porch or lean-to, a chimney, "
                               f"a loft or second storey and a birch or plaster fill between the logs.")
            total = cap
    if not m.dark:
        cap = int(round(DARK_CAP[0] + DARK_CAP[1] * _bright(v)))
        if cap < total:
            looks["cap"] = cap
            findings.insert(0, f"Looks: the house reads dark (mean wall lightness {round(v['wall_l'])}, "
                               f"{round(100 * v['light'])}% light), so the total is held at {cap} (it would be {total}). "
                               f"Light walls and a coloured roof lift the cap; a dark look is fine only when asked.")
            total = cap
    return {"total": total, "building": True, "town": town, "buildings": len(bs), "parts": parts,
            "findings": findings, "fixes": fixes, "weights": weights, "looks": looks}


def weakest(result, n=3):
    """The n weakest parts as [(part, score, [fixes])], weakest first (by lost weighted points)."""
    parts = result.get("parts") or {}
    w = result.get("weights") or WEIGHTS
    order = sorted(parts, key=lambda k: (-(100 - parts[k]) * w.get(k, 0), k))
    return [(k, parts[k], result["fixes"].get(k) or []) for k in order[:n]]


def summary(result):
    if not result.get("building"):
        return "not a building (not scored)"
    town = f" for a town of {result['buildings']} buildings" if result.get("town") else ""
    return (f"{result['total']}/100{town} ("
            + ", ".join(f"{LABELS[k].lower()} {v}" for k, v in result["parts"].items()) + ")")


def gate_text(result, n=3):
    """The refusal text: total, then the n weakest parts with what to fix and where."""
    lines = [f"Quality {result['total']}/100, below the minimum of {QUALITY_MIN}. The weakest parts:"]
    for k, v, fix in weakest(result, n):
        lines.append(f"- {LABELS[k]} {v}/100: " + (" ".join(fix[:2]) if fix else "improve it."))
    return "\n".join(lines)


def built_only(blocks, land):
    """The blocks that were built on a terrain (not the land itself), for scoring builds on terrain."""
    if not land:
        return blocks
    return {p: s for p, s in blocks.items() if land.get(p) != s}


RUBRIC = """Score your build 1-5 on each part (5 = like the reference survival manors):
1. Wall contrast and colours - a light wall fill (birch, oak, stripped logs, plaster) between oak or spruce log posts
   and beams; most of the wall seen from outside is light; a teal or coloured roof, white-framed windows (dark oak,
   deepslate, blackstone only when the user asked for a dark build). 5 = light warm wood like the reference manors,
   1 = the house reads near-black.
2. Storeys - 2-3 floors (a small hut or cottage may have 1), as tall as it is long, not a long low bar.
   5 = 2-3 storeys with a storey band between them, 1 = one long low floor.
3. Windows - big 2 x 2 windows in every bay of every facade with shutters and a sill; soft mixed plants in planters
   under only some lower windows (a row of red flowers under every window reads as red squares). 5 = 12-20% glass on each
   side, 1 = a few small panes.
4. Balconies - balconies and terraces with railings on the upper floors, an outside stair with landings up to one.
   5 = two or more and a stair, 1 = none.
5. Roof colour and layers - a roof colour of its own (teal, green, red) with an oak trim, roofs at 3+ heights
   (storey bands, wing and porch roofs, the main roof). 5 = colored layered roofs, 1 = one roof in the wall wood.
6. Facade depth - log posts and beams stick out 1 block from the wall; no flat wall longer than 5 blocks without a post,
   window or step. 5 = framed walls on every side, 1 = flat plank or stone walls.
7. Roof - pitched stair roof, eaves overhang the walls by 1+, barge boards and ridge in a second material, big roofs
   broken by cross gables or dormers. 5 = layered roof with trims, 1 = flat box top.
8. Massing - a main volume plus a wing, porch, balcony or annex, more than one roof height. 5 = L/T plan with porch and
   balcony, 1 = one box.
9. Palette - 3-6 materials with roles: logs for the frame, one wall fill, a different roof, accents (glass, trapdoors,
   lanterns, fences). 5 = clear roles, 1 = one material or a random mix.
10. Detail - lanterns, pots, shutters, fences, a chimney. 5 = every wall has framed windows and lights, 1 = bare walls.
11. Surroundings - a path to the door, a fenced garden, flowers, a farm plot or terrace, lantern posts. 5 = the house
   sits in a yard, 1 = it stands on nothing.
Fix every part you score below 4 with build_step (pattern() has the proven parts), then call save_build."""
