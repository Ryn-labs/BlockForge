"""Building quality score: is this a good-looking house, or a blocky box?

score(blocks, size=None) -> {"total": 0-100 or None, "building": bool, "parts": {part: 0-100},
                             "findings": [plain sentences with coordinates], "fixes": {part: [what to do, with coordinates]}}

Only buildings are scored: something with at least one closed room (walls on all four sides, a roof over it and 2 blocks
of head room). Bridges, trees, terrain, statues and walls get total None (neutral, never gated).

The six parts and their weights (docs/QUALITY.md has the rules behind the numbers):
  facade 20     wall depth: posts, frames and beams sticking out 1+ from the wall plane (shutters and boxes count less);
                flat runs longer than 5 = penalty
  roof 20       pitched stair/slab roof, eaves overhanging 1+, a trim or ridge in a second material; flat = big penalty
  massing 15    main volume + wings/porch/balcony/annex, more than one roof height; a single box is low
  palette 15    3-6 materials with roles: frame (logs), wall fill, a different roof, accents; 1 material or 10 random = low
  detail 20     windows per facade metre, framed windows, shutters/boxes/lanterns/fences/pots, a chimney
  surroundings 10   a path to the door, garden/fence/farm/terrace/light around the house
"""
import bisect
import collections

from .checks import PATH_BLOCKS, THIN_NAMES, THIN_SUFFIXES, name as _name, props as _props

QUALITY_MIN = 60                     # save_build and the script engine refuse/fix a building below this (one place)
WEIGHTS = {"facade": 20, "roof": 20, "massing": 15, "palette": 15, "detail": 20, "surroundings": 10}
LABELS = {"facade": "Facade depth", "roof": "Roof", "massing": "Massing", "palette": "Palette", "detail": "Detail",
          "surroundings": "Surroundings"}
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


def kind(n):
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
    out = set(cols)
    for (x, z) in cols:
        for a in range(-r, r + 1):
            for c in range(-r, r + 1):
                out.add((x + a, z + c))
    return out


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
        N, S = {}, {}
        for p, s in blocks.items():
            n = _name(s)
            if n in AIR:
                continue
            N[p] = n
            S[p] = s
        self.N, self.S = N, S
        self.K = {p: kind(n) for p, n in N.items()}
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
def _facade(m):
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
            faces.append([d, q, fk, mkey(m.N[q]) if q in m.N else "", t, k == "frame", box])
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
        fix.append("Add a roof trim: the gable edges (barge boards) and the ridge in a second material, e.g. dark oak "
                   "stairs on a spruce roof (pattern gable_roof_trim).")
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
        fix.append("Make the roof a different material from the walls (e.g. spruce or dark oak stairs over oak planks or "
                   "plaster walls).")
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


PARTS = (("facade", _facade), ("roof", _roof), ("massing", _massing), ("palette", _palette), ("detail", _detail),
         ("surroundings", _surroundings))


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


def score(blocks, size=None):
    """Quality of a building, see the module text. `size` (the size hint) is accepted for callers that have it.
    Three or more separate buildings are a town: the total is half the house parts, half the town parts
    (TOWN_WEIGHTS: winding streets that reach the doors, varied houses, open space, a landmark, density)."""
    m = _Model(blocks or {})
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
    return {"total": total, "building": True, "town": town, "buildings": len(bs), "parts": parts,
            "findings": findings, "fixes": fixes, "weights": weights}


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


RUBRIC = """Score your build 1-5 on each part (5 = like a good survival-showcase house):
1. Facade depth - log posts and beams stick out 1 block from the wall; no flat wall longer than 5 blocks without a post,
   window or step. 5 = framed walls on every side, 1 = flat plank or stone walls.
2. Roof - pitched stair roof, eaves overhang the walls by 1+, barge boards and ridge in a second material, big roofs
   broken by cross gables or dormers. 5 = layered roof with trims, 1 = flat box top.
3. Massing - a main volume plus a wing, porch, balcony or annex, more than one roof height. 5 = L/T plan with porch and
   balcony, 1 = one box.
4. Palette - 3-6 materials with roles: logs for the frame, one wall fill, a different roof, accents (glass, trapdoors,
   lanterns, fences). 5 = clear roles, 1 = one material or a random mix.
5. Detail - a window every 3-4 blocks with shutters or a flower box, lanterns, pots, a chimney. 5 = every wall has
   framed windows and lights, 1 = bare walls.
6. Surroundings - a path to the door, a fenced garden, flowers, a farm plot or terrace, lantern posts. 5 = the house sits
   in a yard, 1 = it stands on nothing.
Fix every part you score below 4 with build_step (pattern() has the proven parts), then call save_build."""
