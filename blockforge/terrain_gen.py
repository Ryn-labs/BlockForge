"""Natural terrain: mountains, ranges, valleys and hills that look like land, not like houses.

generate() builds a height map from several layers of smooth gradient noise (warped, so ridges bend), with ridged noise for
sharp mountain crests, then lets loose material slide down (thermal erosion) so no slope steps more than ~2 blocks except on
real cliffs. Edges taper to the ground so the box never shows a straight cut. Blocks follow height and steepness: grass and
dirt on gentle ground, banded stone / andesite / tuff on steep faces, gravel scree at the foot of cliffs, snow above the
snow line, trees that thin out with height, a few boulders and (valley) a winding river.

Pure and deterministic: the same arguments always give the same blocks. No game or app needed."""
import math
import random

KINDS = ("mountain", "range", "valley", "hills")
PODZOL, MOSS = "minecraft:podzol", "minecraft:moss_block"
GRASS, DIRT, COARSE, SNOW, GRAVEL = ("minecraft:grass_block", "minecraft:dirt", "minecraft:coarse_dirt",
                                     "minecraft:snow_block", "minecraft:gravel")
WATER, SAND, CLAY = "minecraft:water", "minecraft:sand", "minecraft:clay"
ROCKS = ("minecraft:stone", "minecraft:andesite", "minecraft:stone", "minecraft:tuff", "minecraft:stone", "minecraft:andesite")
BOULDER = ("minecraft:stone", "minecraft:andesite", "minecraft:mossy_cobblestone", "minecraft:cobblestone")
MAX_AREA_SOLID = 160 * 160          # bigger boxes get a thick shell instead of solid rock (keeps block counts sane)


class Noise:
    """2-D gradient (Perlin) noise, -1..1, seeded."""

    def __init__(self, seed):
        rng = random.Random(seed)
        p = list(range(256))
        rng.shuffle(p)
        self.p = p + p
        self.g = [(math.cos(a), math.sin(a)) for a in (rng.random() * 2 * math.pi for _ in range(256))]

    def __call__(self, x, y):
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        xi &= 255
        yi &= 255
        p, g = self.p, self.g

        def dot(ix, iy, dx, dy):
            gx, gy = g[p[p[ix] + iy] & 255]
            return gx * dx + gy * dy
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
        v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)
        n00 = dot(xi, yi, xf, yf)
        n10 = dot(xi + 1, yi, xf - 1, yf)
        n01 = dot(xi, yi + 1, xf, yf - 1)
        n11 = dot(xi + 1, yi + 1, xf - 1, yf - 1)
        a = n00 + (n10 - n00) * u
        b = n01 + (n11 - n01) * u
        return (a + (b - a) * v) * 1.41


def _fbm(n, x, y, octaves=5, lac=2.0, gain=0.5):
    s, amp, f, norm = 0.0, 1.0, 1.0, 0.0
    for _ in range(octaves):
        s += amp * n(x * f, y * f)
        norm += amp
        amp *= gain
        f *= lac
    return s / norm


def _ridged(n, x, y, octaves=5):
    """Sharp crests: 0..1, high on the ridge lines."""
    s, amp, f, norm, w = 0.0, 1.0, 1.0, 0.0, 1.0
    for _ in range(octaves):
        r = 1.0 - abs(n(x * f, y * f))
        r *= r * w
        w = max(0.0, min(1.0, r * 2.0))
        s += r * amp
        norm += amp
        amp *= 0.5
        f *= 2.0
    return s / norm


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def heightmap(w, l, kind="mountain", height=60, seed=0, base=3, river=None):
    """Float heights h[z][x] above y=0. Returns (h, river_cells, water_y, cliff) with river_cells a set of (x, z)."""
    if kind not in KINDS:
        raise ValueError("kind must be one of " + ", ".join(KINDS))
    n1, n2, n3, n4 = Noise(seed), Noise(seed + 101), Noise(seed + 202), Noise(seed + 303)
    size = max(w, l)
    sc = 1.0 / max(48.0, size * 0.55)                     # feature size follows the box: a 300 wide range is not 300 tiny hills
    cx = w * (0.5 + 0.12 * n4(seed * 0.37 + 0.5, 0.5))
    cz = l * (0.5 + 0.12 * n4(0.5, seed * 0.37 + 0.5))
    long_x = w >= l
    river = (kind == "valley") if river is None else river
    h = [[0.0] * w for _ in range(l)]
    cliff = [[False] * w for _ in range(l)]
    prng = random.Random(seed * 31 + 7)
    side = []                                                     # foothills / side peaks around the main mountain
    if kind == "mountain":
        for k in range(prng.randint(3, 4)):
            a = prng.random() * 2 * math.pi
            d = prng.uniform(0.26, 0.40)
            side.append((cx + math.cos(a) * d * w, cz + math.sin(a) * d * l, prng.uniform(0.10, 0.17) * size,
                         prng.uniform(0.22, 0.46)))
    for z in range(l):
        for x in range(w):
            wx = x + 18 * _fbm(n2, x * sc * 1.3, z * sc * 1.3, 3)            # domain warp: ridges bend, nothing is round
            wz = z + 18 * _fbm(n3, x * sc * 1.3 + 7.1, z * sc * 1.3 + 3.3, 3)
            detail = _fbm(n1, wx * sc * 2.0, wz * sc * 2.0, 5)                # -1..1
            ridge = _ridged(n1, wx * sc * 1.1 + 31.7, wz * sc * 1.1 + 11.3, 5)
            roll = 0.5 + 0.5 * _fbm(n4, wx * sc * 1.7 + 40.0, wz * sc * 1.7 + 40.0, 4)
            foot = 0.09 * roll + 0.03 * detail                                 # rolling foothills everywhere: no flat plate
            if kind == "mountain":
                dx, dz = (wx - cx) / (w * 0.46), (wz - cz) / (l * 0.46)
                r = math.sqrt(dx * dx + dz * dz) * (1.0 + 0.35 * _fbm(n4, wx * sc * 0.9, wz * sc * 0.9, 3))
                mask = 1.0 - _smooth(r)
                shoulders = 0.5 + 0.5 * _fbm(n2, wx * sc * 0.8 + 9.0, wz * sc * 0.8 + 4.0, 3)   # side peaks and saddles
                ang = math.atan2(dz, dx)
                spokes = abs(math.sin(ang * 2.5 + seed + 2.0 * _fbm(n2, wx * sc * 0.7, wz * sc * 0.7, 2))) ** 0.6
                arms = 1.0 - (1.0 - (0.55 + 0.45 * spokes)) * min(1.0, r * 1.7)    # ridges out from the top, gullies between
                core = mask ** 1.1 * (0.30 + 0.45 * ridge + 0.25 * shoulders) * arms + 0.08 * detail * mask
                peaks = max(0.0, core) ** 3
                for px, pz, rad, amp in side:
                    dd = ((wx - px) ** 2 + (wz - pz) ** 2) / (2 * rad * rad)
                    peaks += (amp * math.exp(-dd) * (0.65 + 0.35 * ridge)) ** 3
                v = peaks ** (1.0 / 3.0) + foot
            elif kind in ("range", "valley"):
                across = ((wz / l) if long_x else (wx / w))
                along = ((wx / w) if long_x else (wz / l))
                bend = 0.08 * math.sin(along * math.pi * 2.1 + seed) + 0.06 * _fbm(n4, along * 3.0, 0.3, 3)
                if kind == "range":
                    d = abs(across - (0.5 + bend)) / 0.42
                    mask = 1.0 - _smooth(d)
                else:                                                          # two ridges, low floor between them
                    d = abs(across - (0.5 + bend))
                    mask = _smooth((d - 0.07) / 0.30) * (1.0 - _smooth((d - 0.40) / 0.12))
                v = mask ** 1.2 * (0.55 + 0.45 * ridge) + 0.05 * detail + foot
            else:                                                              # hills: rolling, no crests
                v = 0.5 + 0.38 * _fbm(n1, wx * sc * 1.6, wz * sc * 1.6, 4) + 0.12 * detail
            edge = min(x, z, w - 1 - x, l - 1 - z)
            low = 0.02 + 0.05 * roll                                          # the edge is low rolling land, not a flat rim
            v = low + (v - low) * _smooth(edge / max(6.0, min(w, l) * 0.12))  # soft edges: the land meets the ground, no cut
            h[z][x] = base + max(0.0, v) * height
            cliff[z][x] = kind != "hills" and ridge > 0.72 and v > 0.45       # real rock faces may stay steep
    peak = max(max(row) for row in h)
    f = min(1.6, height * 1.04 / max(1.0, peak - base))                   # the highest ground reaches the asked height
    for row in h:                                                           # (scaled BEFORE erosion: erosion sets the slopes)
        for x in range(w):
            row[x] = base + (row[x] - base) * f
    _erode(h, cliff, w, l, iters=16 if kind != "hills" else 12)
    for z in range(l):
        row = h[z]
        for x in range(w):
            edge = min(x, z, w - 1 - x, l - 1 - z)
            up = min(1.0, (row[x] - base) / 6.0)
            wobble = 2.6 * _fbm(n2, x / 13.0 + 5.5, z / 13.0 + 2.2, 2) * up      # slope varies: steps never land at even spacing
            fine = (1.0 * _fbm(n3, x / 4.5 + 3.3, z / 4.5 + 8.8, 3)) * _smooth(edge / 6.0) * up   # wiggly contour lines
            row[x] = row[x] + wobble + fine
    river_cells, water_y = set(), None
    if river:
        river_cells, water_y = _carve_river(h, w, l, base, height, long_x, n4, seed)
    return h, river_cells, water_y, cliff


def _erode(h, cliff, w, l, iters):
    """Thermal erosion: where a cell stands more than `talus` above a neighbour, part of the difference slides down."""
    for it in range(iters):
        for z in range(l):
            row = h[z]
            for x in range(w):
                c = row[x]
                talus = 5.0 if cliff[z][x] else 2.6
                lo, lx, lz = c, x, z
                for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                    if 0 <= nx < w and 0 <= nz < l and h[nz][nx] < lo:
                        lo, lx, lz = h[nz][nx], nx, nz
                d = c - lo
                if d > talus:
                    m = (d - talus) * 0.5
                    row[x] -= m
                    h[lz][lx] += m


def _carve_river(h, w, l, base, height, long_x, n, seed):
    water_y = int(round(base + 0.05 * height)) + 2
    cells = set()
    span = w if long_x else l
    across = l if long_x else w
    half = max(2.0, across * 0.022)
    for t in range(span):
        u = t / max(1, span - 1)
        c = across * (0.5 + 0.08 * math.sin(u * math.pi * 2.1 + seed) + 0.06 * _fbm(n, u * 3.0, 0.3, 3))
        c += across * 0.035 * math.sin(u * math.pi * 7.3 + seed * 0.7)
        for k in range(int(c - half * 4), int(c + half * 4) + 1):
            if not (0 <= k < across):
                continue
            x, z = (t, k) if long_x else (k, t)
            d = abs(k - c)
            if d <= half:
                cells.add((x, z))
                h[z][x] = water_y - 1.6 - 1.2 * (1 - d / half)                 # channel bed 2-3 under the water
            elif d <= half * 4:
                bank = water_y + 1 + (d - half) * 0.55                          # banks rise gently, never below the water
                h[z][x] = min(max(h[z][x], water_y + 1), max(bank, water_y + 1)) if h[z][x] < bank else h[z][x]
    return cells, water_y


def _rock(x, y, z, n):
    band = int((y + 4.0 * n(x / 23.0, z / 23.0)) // 4) % len(ROCKS)     # strata: bands that wander a little
    return ROCKS[band]


def generate(w, l, kind="mountain", height=60, seed=0, base=2, snowline=None, trees=True, boulders=True,
             river=None, solid=None, shell=10):
    """Blocks {(x, y, z): state} with (0, 0, 0) at the box corner, and an info dict.

    kind: mountain (one massif), range (a ridge along the long side), valley (two ridges with a river), hills (rolling).
    height: rise of the highest ground above `base`. snowline: y where snow starts (default 72% of the height for
    mountains, none for hills; pass a number or False). solid: fill to y=0 (default when the box is up to 160 x 160),
    else a rock shell `shell` blocks thick under the surface."""
    if w < 8 or l < 8 or height < 4:
        raise ValueError("terrain needs at least 8 x 8 and a height of 4")
    h, river_cells, water_y, cliff = heightmap(w, l, kind, height, seed, base, river)
    top = [[int(round(v)) for v in row] for row in h]
    if snowline is None:
        snowline = None if kind == "hills" else int(base + 0.72 * height)
    elif snowline is False:
        snowline = None
    treeline = (snowline - 6) if snowline else base + int(0.85 * height)
    solid = (w * l <= MAX_AREA_SOLID) if solid is None else solid
    n = Noise(seed + 404)
    rng = random.Random(seed * 7919 + 17)
    blocks = {}

    def slope(x, z):
        c, s = top[z][x], 0
        for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if 0 <= nx < w and 0 <= nz < l:
                s = max(s, abs(c - top[nz][nx]))
        return s

    sl = [[slope(x, z) for x in range(w)] for z in range(l)]
    steep_near = [[False] * w for _ in range(l)]
    for z in range(l):
        for x in range(w):
            if sl[z][x] >= 4:
                for a in range(-2, 3):
                    for b in range(-2, 3):
                        if 0 <= x + a < w and 0 <= z + b < l:
                            steep_near[z + b][x + a] = True
    surface = {}
    for z in range(l):
        for x in range(w):
            y, s = top[z][x], sl[z][x]
            jitter = 3.0 * n(x / 9.0, z / 9.0)
            patch = n(x / 13.0 + 50, z / 13.0 + 50)
            if (x, z) in river_cells:
                kind_top = "bed"
            elif snowline and y + jitter >= snowline:
                kind_top = "snow" if s <= 2 else "rock"
            elif s >= 3:
                kind_top = "rock"
            elif steep_near[z][x] and y < (snowline or 10 ** 6) - 3:
                kind_top = "scree"
            elif y > treeline + jitter:
                kind_top = "alpine"
            else:
                kind_top = "grass"
            surface[(x, z)] = kind_top
            low = 0
            if not solid:
                mn = y
                for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                    if 0 <= nx < w and 0 <= nz < l:
                        mn = min(mn, top[nz][nx])
                low = max(0, mn - shell)
            for yy in range(low, y + 1):
                d = y - yy
                if kind_top == "snow":
                    st = SNOW if d == 0 else _rock(x, yy, z, n)
                elif kind_top == "rock":
                    st = _rock(x, yy, z, n)
                elif kind_top == "scree":
                    st = (GRAVEL if patch > -0.25 else "minecraft:andesite") if d <= 1 else _rock(x, yy, z, n)
                elif kind_top == "bed":
                    st = (GRAVEL if patch > 0 else SAND) if d == 0 else (CLAY if d == 1 and patch < -0.3 else DIRT if d <= 2 else _rock(x, yy, z, n))
                elif kind_top == "alpine":
                    st = ((COARSE if patch > 0.5 else GRASS) if d == 0 else DIRT) if d <= 1 else _rock(x, yy, z, n)
                elif d == 0:                                                         # mixed ground, not one flat green
                    p2 = n(x / 6.5 + 90.0, z / 6.5 + 90.0)
                    rise = (y - base) / max(1.0, treeline - base)
                    st = (COARSE if patch > 0.62 else PODZOL if p2 > 0.5 and rise > 0.3 else MOSS if p2 < -0.55 else GRASS)
                else:
                    st = DIRT if d <= 3 else _rock(x, yy, z, n)
                blocks[(x, yy, z)] = st
            if (x, z) in river_cells and water_y:
                for yy in range(y + 1, water_y + 1):
                    blocks[(x, yy, z)] = WATER
            elif water_y and kind_top == "grass" and y == water_y + 1 and patch > 0.1 and any(
                    (x + a, z + b) in river_cells for a in (-1, 0, 1) for b in (-1, 0, 1)):
                blocks[(x, y, z)] = SAND                                                # sandy bank right at the water
    n_trees = n_boulders = 0
    if boulders:
        for _ in range(max(1, w * l // 900)):
            x, z = rng.randrange(3, w - 3), rng.randrange(3, l - 3)
            if surface[(x, z)] not in ("grass", "scree", "alpine") or sl[z][x] > 2:
                continue
            y, r = top[z][x], rng.choice((1.2, 1.6, 2.1))
            st = rng.choice(BOULDER)
            for a in range(-2, 3):
                for b in range(-1, 3):
                    for c in range(-2, 3):
                        if (a * a) / (r * r) + (b * b) / (r * r * 0.7) + (c * c) / (r * r) <= 1.0:
                            blocks[(x + a, y + b, z + c)] = st if rng.random() > 0.2 else "minecraft:mossy_cobblestone"
            n_boulders += 1
    if trees:
        taken = set()
        forest = Noise(seed + 505)
        for z in range(2, l - 2):
            for x in range(2, w - 2):
                if surface[(x, z)] != "grass" or sl[z][x] > 1:
                    continue
                y = top[z][x]
                rise = (y - base) / max(1.0, treeline - base)
                if rise >= 1.0:
                    continue
                chance = 0.016 * (1.0 - rise) ** 1.4 * (0.45 + 0.9 * max(0.0, forest(x / 31.0, z / 31.0) + 0.35))
                if rng.random() > chance or any((x + a, z + b) in taken for a in range(-2, 3) for b in range(-2, 3)):
                    continue
                taken.add((x, z))
                _tree(blocks, x, y + 1, z, "spruce" if rise > 0.45 or rng.random() < 0.3 else rng.choice(("oak", "oak", "birch")), rng)
                n_trees += 1
    if trees:                                                                     # grass tufts and ferns: texture, not a flat lawn
        for z in range(l):
            for x in range(w):
                y = top[z][x]
                if surface[(x, z)] == "grass" and blocks.get((x, y, z)) in (GRASS, PODZOL, MOSS) and (x, y + 1, z) not in blocks                         and rng.random() < 0.09:
                    blocks[(x, y + 1, z)] = "minecraft:fern" if (y - base) > 0.4 * (treeline - base) else "minecraft:short_grass"
    peak = max(max(row) for row in top)
    info = {"kind": kind, "size": [w, l], "peak_y": peak, "base": base, "snowline": snowline, "treeline": treeline,
            "water_y": water_y, "river_cells": len(river_cells), "trees": n_trees, "boulders": n_boulders,
            "solid": solid, "blocks": len(blocks), "seed": seed}
    return blocks, info


def _tree(blocks, x, y, z, kind, rng):
    log, leaf = f"minecraft:{kind}_log", f"minecraft:{kind}_leaves[persistent=true]"
    if kind == "spruce":
        hgt = rng.randint(6, 10)
        for k in range(hgt):
            blocks[(x, y + k, z)] = log
        for k in range(2, hgt + 1):
            r = max(0, (hgt - k) // 2 - (k % 2))
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    if abs(a) + abs(b) <= r + (r > 1) and (a or b) and (x + a, y + k, z + b) not in blocks:
                        blocks[(x + a, y + k, z + b)] = leaf
        blocks[(x, y + hgt, z)] = leaf
        blocks[(x, y + hgt + 1, z)] = leaf
        return
    hgt = rng.randint(4, 6)
    for k in range(hgt):
        blocks[(x, y + k, z)] = log
    cy = y + hgt - 1
    for a in range(-2, 3):
        for b in range(-1, 3):
            for c in range(-2, 3):
                if a * a + c * c + (b * b) * 1.6 <= 5.2 and (a or c or b > 0) and (x + a, cy + b, z + c) not in blocks:
                    if not (abs(a) == 2 and abs(c) == 2 and rng.random() < 0.6):
                        blocks[(x + a, cy + b, z + c)] = leaf
