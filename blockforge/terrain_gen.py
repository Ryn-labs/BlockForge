"""Natural terrain: mountains, ranges, valleys and hills that look like land, not like houses.

generate() builds a height map from several layers of smooth gradient noise (warped, so ridges bend), with ridged noise for
sharp mountain crests, then lets loose material slide down (thermal erosion) so no slope steps more than ~2 blocks except on
real cliffs. Edges taper to the ground so the box never shows a straight cut. Blocks follow height and steepness: grass and
dirt on gentle ground, banded stone / andesite / tuff on steep faces, gravel scree at the foot of cliffs, snow above the
snow line, trees that thin out with height, a few boulders and (valley) a winding river.

Round 2 (the default look; each knob 0..1, 0 = the smooth 1.16 look):
- ruggedness: a broad massif with 2-3 extra summits and saddles, a blunt main summit set off its centre, crags and crumbly
  rock so no face is an even ramp.
- ledges: shoulders (flat-topped spurs) and benches from hard / soft rock layers - soft layers erode back into ledges,
  hard ones stay as short risers; the layers sit at random heights, wander across the contours and fade in and out.
- snow_mix: snow lies on ledges and gentle ground above a fuzzy snowline (and on flat ledges a bit lower); steep faces,
  downhill streaks and blotches show dark rock (deepslate, tuff, andesite); alpine ground mixes rock, scree and turf.
A last settling pass keeps every step at 3 blocks or less except on marked cliffs.

Pure and deterministic: the same arguments always give the same blocks. No game or app needed."""
import bisect
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
DARK = ("minecraft:deepslate", "minecraft:tuff", "minecraft:andesite", "minecraft:cobbled_deepslate", "minecraft:stone",
        "minecraft:tuff")                                                    # bare rock high up: dark, mixed, never one grey
RUGGED, LEDGES, SNOW_MIX = 0.6, 0.6, 0.6                                     # the default look (0 = the smooth 1.16 look)
LEDGE_SNOW = 10.0                                                            # snow on flat ledges down to this below the snowline


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


def heightmap(w, l, kind="mountain", height=60, seed=0, base=3, river=None, ruggedness=RUGGED, ledges=LEDGES):
    """Float heights h[z][x] above y=0. Returns (h, river_cells, water_y, cliff) with river_cells a set of (x, z).
    ruggedness 0..1: crags and slopes that change steepness. ledges 0..1: benches / shoulders on some slopes."""
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
    rug = max(0.0, min(1.0, float(ruggedness)))
    steep = max(0.0, min(1.0, height / (0.5 * min(w, l)) - 0.7))              # tall for its box: use more of the box
    led = max(0.0, min(1.0, float(ledges)))
    srng = random.Random(seed * 977 + 13)
    tops = []                                                     # more summits on the massif: saddles between them
    stretch = (1.0, 0.0, 1.0)
    if kind == "mountain" and rug > 0:
        a0 = srng.random() * 2 * math.pi
        for k in range(srng.randint(2, 3)):
            a = a0 + k * srng.uniform(1.6, 2.6)
            d = srng.uniform(0.13, 0.24)
            tops.append((cx + math.cos(a) * d * w, cz + math.sin(a) * d * l, srng.uniform(0.09, 0.14) * size,
                         srng.uniform(0.66, 0.86)))
        t = srng.random() * math.pi                                # the massif is longer one way: no round cone
        stretch = (math.cos(t), math.sin(t), 1.0 + 0.45 * rug)
    shelves = []                                                  # shoulders: flat-topped spurs half way up the flanks
    if kind == "mountain" and led > 0:
        for k in range(srng.randint(4, 6)):
            a = srng.random() * 2 * math.pi
            d = srng.uniform(0.12, 0.27)
            shelves.append((cx + math.cos(a) * d * w, cz + math.sin(a) * d * l, srng.uniform(0.05, 0.09) * size,
                            srng.uniform(0.3, 0.75) * (1.15 - d * 1.6), math.cos(a), math.sin(a)))
    for z in range(l):
        for x in range(w):
            wx = x + 18 * _fbm(n2, x * sc * 1.3, z * sc * 1.3, 3)            # domain warp: ridges bend, nothing is round
            wz = z + 18 * _fbm(n3, x * sc * 1.3 + 7.1, z * sc * 1.3 + 3.3, 3)
            detail = _fbm(n1, wx * sc * 2.0, wz * sc * 2.0, 5)                # -1..1
            ridge = _ridged(n1, wx * sc * 1.1 + 31.7, wz * sc * 1.1 + 11.3, 5)
            roll = 0.5 + 0.5 * _fbm(n4, wx * sc * 1.7 + 40.0, wz * sc * 1.7 + 40.0, 4)
            foot = 0.09 * roll + 0.03 * detail                                 # rolling foothills everywhere: no flat plate
            if kind == "mountain":
                spread = 0.46 + rug * (0.08 + 0.12 * steep)                    # a broad massif leaves room for ledges
                dx, dz = (wx - cx) / (w * spread), (wz - cz) / (l * spread)
                ca, sa, st = stretch
                along, across = (dx * ca + dz * sa) / st, (dz * ca - dx * sa)
                r = math.sqrt(along * along + across * across) * (1.0 + 0.35 * _fbm(n4, wx * sc * 0.9, wz * sc * 0.9, 3))
                mask = 1.0 - _smooth(r)
                if rug > 0:                                                    # straighter flank: no steep bell middle
                    mask += 0.5 * rug * ((1.0 - min(1.0, r)) ** 1.2 - mask)
                shoulders = 0.5 + 0.5 * _fbm(n2, wx * sc * 0.8 + 9.0, wz * sc * 0.8 + 4.0, 3)   # side peaks and saddles
                ang = math.atan2(dz, dx)
                spokes = abs(math.sin(ang * 2.5 + seed + 2.0 * _fbm(n2, wx * sc * 0.7, wz * sc * 0.7, 2))) ** 0.6
                arms = 1.0 - (1.0 - (0.55 + 0.45 * spokes)) * min(1.0, r * 1.7)    # ridges out from the top, gullies between
                core = mask ** 1.1 * (0.30 + 0.45 * ridge + 0.25 * shoulders) * arms + 0.08 * detail * mask
                core = max(0.0, core)
                if rug > 0 and core > 0.5:                                    # blunt main top: no needle
                    e = core - 0.5
                    core = 0.5 + e / (1.0 + 1.6 * rug * e)
                peaks = core ** 3
                for px, pz, rad, amp in side:
                    dd = ((wx - px) ** 2 + (wz - pz) ** 2) / (2 * rad * rad)
                    peaks += (amp * math.exp(-dd) * (0.65 + 0.35 * ridge)) ** 3
                for px, pz, rad, amp in tops:                                  # second / third summits
                    dd = ((wx - px) ** 2 + (wz - pz) ** 2) / (2 * rad * rad)
                    peaks += (amp * 0.72 * math.exp(-dd) * (0.7 + 0.3 * ridge) * mask ** 0.3) ** 3
                for sx, sz, rs, hs, ca, sa in shelves:
                    ex, ez = wx - sx, wz - sz
                    u, t = (ex * ca + ez * sa) / (rs * 1.7), (ez * ca - ex * sa) / rs
                    q = math.sqrt(u * u + t * t)
                    if q < 1.3:
                        sv = led * hs * (1.0 + 0.08 * detail) * (1.0 - _smooth((q - 0.4) / 0.85))
                        peaks += max(0.0, sv) ** 3
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
            if rug > 0 and kind != "hills":                                    # crags: knobs and notches on the slopes
                up = _smooth((v - 0.12) / 0.25)
                v += rug * 0.07 * (_ridged(n3, wx * sc * 3.4 + 5.0, wz * sc * 3.4 + 9.0, 3) - 0.42) * up
            edge = min(x, z, w - 1 - x, l - 1 - z)
            low = 0.02 + 0.05 * roll                                          # the edge is low rolling land, not a flat rim
            v = low + (v - low) * _smooth(edge / max(6.0, min(w, l) * 0.12))  # soft edges: the land meets the ground, no cut
            h[z][x] = base + max(0.0, v) * height
            cliff[z][x] = kind != "hills" and ridge > 0.72 and v > 0.45       # real rock faces may stay steep
    horn = 0.3 * rug if kind == "mountain" else 0.0                        # share of the height in the summit block
    peak = max(max(row) for row in h)
    f = min(1.6, height * 1.04 * (1.0 - horn) / max(1.0, peak - base))    # the highest ground reaches the asked height
    for row in h:                                                           # (scaled BEFORE erosion: erosion sets the slopes)
        for x in range(w):
            row[x] = base + (row[x] - base) * f
    if horn > 0:
        _summit(h, w, l, base, height, size, rug, srng, n1, n2)
    talus = None
    if rug > 0:                                                             # some faces erode steeper than others
        tn = Noise(seed + 606)
        talus = [[2.6 + 0.45 * rug * max(-1.0, min(1.0, 1.4 * _fbm(tn, x / 17.0, z / 17.0, 2))) for x in range(w)]
                 for z in range(l)]
    bands = _bands(w, l, base, height, led * (0.5 if kind == "hills" else 1.0), srng, sc, n2, n3, n4) if led > 0 else None
    _erode(h, cliff, w, l, iters=16 if kind != "hills" else 12, talus=talus, bands=bands, base=base)
    for z in range(l):
        row = h[z]
        for x in range(w):
            edge = min(x, z, w - 1 - x, l - 1 - z)
            up = min(1.0, (row[x] - base) / 6.0)
            wobble = 2.6 * _fbm(n2, x / 13.0 + 5.5, z / 13.0 + 2.2, 2) * up      # slope varies: steps never land at even spacing
            fine = (1.0 * _fbm(n3, x / 4.5 + 3.3, z / 4.5 + 8.8, 3)) * _smooth(edge / 6.0) * up   # wiggly contour lines
            row[x] = row[x] + wobble + fine
    if rug > 0:                                                             # crumbly rock: small ledges and knobs, so a
        cn = Noise(seed + 808)                                              # steep face never reads as an even ramp
        crumb = rug * (0.6 if kind == "hills" else 1.0)
        for z in range(l):
            row = h[z]
            for x in range(w):
                edge = min(x, z, w - 1 - x, l - 1 - z)
                up = _smooth((row[x] - base - 4.0) / 10.0) * _smooth(edge / 8.0)
                if up > 0:
                    row[x] += crumb * up * (0.9 * _fbm(cn, x / 3.3, z / 3.3, 2) + 0.5 * cn(x / 1.6 + 40.0, z / 1.6 + 40.0))
    _settle(h, cliff, w, l)
    river_cells, water_y = set(), None
    if river:
        river_cells, water_y = _carve_river(h, w, l, base, height, long_x, n4, seed)
        _settle(h, cliff, w, l, fixed=river_cells)                         # the banks too; the channel stays as cut
    return h, river_cells, water_y, cliff


def _settle(h, cliff, w, l, limit=2.95, fixed=()):
    """Last pass: no step over 3 blocks anywhere except on marked cliffs. Where two neighbours differ by more than
    `limit` the extra slides down (half each way), repeated until nothing moves - so crumbs, ledges and the wobble
    never leave a wall (a float difference under 3 can never round to a 4 step)."""
    todo = {(x, z) for z in range(l) for x in range(w)}
    guard = 0
    while todo and guard < 60 * w * l:
        x, z = todo.pop()
        guard += 1
        if cliff[z][x] or (x, z) in fixed:
            continue
        for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if 0 <= nx < w and 0 <= nz < l and not cliff[nz][nx] and (nx, nz) not in fixed:
                d = h[z][x] - h[nz][nx]
                if abs(d) > limit:
                    m = (abs(d) - limit) * 0.5 + 1e-6
                    if d > 0:
                        h[z][x] -= m
                        h[nz][nx] += m
                    else:
                        h[z][x] += m
                        h[nz][nx] -= m
                    for cx, cz in ((x, z), (nx, nz)):
                        for ax, az in ((cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1), (cx, cz)):
                            if 0 <= ax < w and 0 <= az < l:
                                todo.add((ax, az))


def _summit(h, w, l, base, height, size, rug, rng, n1, n2):
    """The main summit on the broad massif: a blunt, lopsided rock block with arms, rising to the asked height. It sits
    a little off the massif's own top (no round cone around one point); erosion then cuts its ledges like the rest."""
    best, sx, sz = -1.0, w // 2, l // 2
    m = max(3, int(min(w, l) * 0.2))
    for z in range(m, l - m):
        for x in range(m, w - m):
            if h[z][x] > best:
                best, sx, sz = h[z][x], x, z
    for k in range(6):                                                      # off the top, but still on high ground
        a = rng.random() * 2 * math.pi
        tx = int(max(m, min(w - 1 - m, sx + math.cos(a) * size * 0.07)))
        tz = int(max(m, min(l - 1 - m, sz + math.sin(a) * size * 0.07)))
        if best - h[tz][tx] < 0.1 * height:
            sx, sz = tx, tz
            break
    rise = base + height * 0.96 - h[sz][sx]                                 # erosion and wobble bring it to ~1.0
    if rise <= 0:
        return
    rad = max(5.0, size * (0.10 + 0.05 * rug), rise / 2.2)                  # never steeper than ~2.2 on average
    t = rng.random() * math.pi
    ca, sa = math.cos(t), math.sin(t)
    for z in range(max(0, int(sz - rad * 2)), min(l, int(sz + rad * 2) + 1)):
        for x in range(max(0, int(sx - rad * 2)), min(w, int(sx + rad * 2) + 1)):
            dx, dz = x - sx, z - sz
            wx = dx + 3.0 * _fbm(n2, x / 9.0 + 4.0, z / 9.0, 2)
            wz = dz + 3.0 * _fbm(n2, x / 9.0, z / 9.0 + 4.0, 2)
            a, b = (wx * ca + wz * sa) / 1.35, (wz * ca - wx * sa)          # longer one way: a ridge top, not a point
            d = math.sqrt(a * a + b * b) / rad
            if d >= 1.6:
                continue
            arms = 1.0 - 0.3 * (1.0 - _ridged(n1, x / 11.0 + 70.0, z / 11.0 + 30.0, 3)) * min(1.0, d)
            bump = 1.0 - _smooth((d - 0.22) / 1.38)                         # a blunt top a few blocks wide, no needle
            h[z][x] += rise * bump * arms


def _bands(w, l, base, height, led, rng, sc, n2, n3, n4):
    """Hard and soft rock layers for erosion: soft layers wear back into benches, hard ones stay as short steep risers.
    The layers sit at random heights (4-9 blocks apart), tilt and wander across the contours and fade in and out along
    the slopes (some faces have ledges, others none), so the benches never form rings."""
    levels = [base + rng.uniform(1.0, 4.0)]
    while levels[-1] < base + height * 1.8 + 12:
        levels.append(levels[-1] + rng.uniform(4.0, 9.0))
    warp, mask, hard = [], [], []
    for z in range(l):
        wr, mr, hr = [], [], []
        for x in range(w):
            wr.append(4.0 * _fbm(n2, x * sc * 2.3 + 3.0, z * sc * 2.3 + 8.0, 2) + 0.06 * (x - w / 2) * math.sin(base + 1.3))
            edge = min(x, z, w - 1 - x, l - 1 - z)                          # no benches pushed out onto the box edge
            mr.append(_smooth((_fbm(n3, x * sc * 1.6 + 17.0, z * sc * 1.6 + 5.0, 3) + 0.7 * led - 0.22) / 0.22)
                      * _smooth((edge - 2.0) / 7.0))
            hr.append(0.28 + 0.2 * (0.5 + 0.5 * _fbm(n4, x * sc * 2.0 + 61.0, z * sc * 2.0 + 7.0, 2)))
        warp.append(wr)
        mask.append(mr)
        hard.append(hr)
    return levels, warp, mask, hard


def _erode(h, cliff, w, l, iters, talus=None, bands=None, base=0):
    """Thermal erosion: where a cell stands more than `talus` above a neighbour, part of the difference slides down.
    talus: None (2.6 everywhere) or a per-cell grid. bands: _bands(...) - soft layers erode flat, hard ones stay steep."""
    if bands:
        levels, warp, mask, hard = bands
    for it in range(iters):
        for z in range(l):
            row = h[z]
            trow = talus[z] if talus else None
            for x in range(w):
                c = row[x]
                talus_c = 5.0 if cliff[z][x] else (trow[x] if trow else 2.6)
                if bands and not cliff[z][x]:
                    m = mask[z][x] * _smooth((c - base - 3.0) / 5.0)
                    if m > 0.03:
                        v = c + warp[z][x]
                        i = bisect.bisect_right(levels, v) - 1
                        lo_, hi_ = levels[max(0, i)], levels[min(len(levels) - 1, i + 1)]
                        t = (v - lo_) / max(0.1, hi_ - lo_)
                        talus_c += m * ((2.7 if t > 1.0 - hard[z][x] else 0.8) - talus_c)
                lo, lx, lz = c, x, z
                for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
                    if 0 <= nx < w and 0 <= nz < l and h[nz][nx] < lo:
                        lo, lx, lz = h[nz][nx], nx, nz
                d = c - lo
                if d > talus_c:
                    m = (d - talus_c) * 0.5
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
    band = int((y + 4.0 * n(x / 23.0, z / 23.0) + 2.5 * n(x / 6.0 + 5.0, z / 6.0 + 5.0)) // 4) % len(ROCKS)   # strata: bands
    #                                                                     that wander and break up, never clean stripes
    return ROCKS[band]


def _dark(x, y, z, n):
    """Bare high rock: deepslate, tuff, andesite and stone in blotches, not one grey."""
    v = n(x / 5.0 + 0.37 * y / 5.0 + 70.0, z / 5.0 - 0.21 * y / 5.0 + 70.0) + 0.35 * n(x / 2.1 + 9.0, z / 2.1 + y / 3.0)
    return DARK[min(len(DARK) - 1, max(0, int((v + 1.0) * len(DARK) / 2.0)))]


def _streaks(top, w, l, kind, n):
    """-1..1 streak noise that runs downhill: rock ribs and gullies from the summit (mountain) or across the ridge."""
    out = [[0.0] * w for _ in range(l)]
    if kind == "mountain":
        pz = max(range(l), key=lambda z: max(top[z]))
        px = max(range(w), key=lambda x: top[pz][x])
        ns = 22.0
        for z in range(l):
            for x in range(w):
                u = (math.atan2(z - pz, x - px) + math.pi) / (2 * math.pi) * ns
                r = math.hypot(x - px, z - pz) / 11.0
                t = u / ns                                                  # blend across the seam: no line at one angle
                out[z][x] = n(u, r) * (1.0 - t) + n(u - ns, r) * t
    else:
        long_x = w >= l
        for z in range(l):
            for x in range(w):
                a, c = (x, z) if long_x else (z, x)
                out[z][x] = n(a / 2.4, c / 11.0)
    return out


def _snow_or_rock(x, z, y, s, snowline, peak_y, mix, streak, n):
    """Snow lies on ledges and gentle ground above a fuzzy snowline; steep faces, rock ribs and blotches stay bare.
    Returns 'snow', 'crag' or None (below the snow: the usual ground)."""
    fuzz = 2.6 * n(x / 9.0, z / 9.0) + 1.2 * mix * n(x / 23.0 + 11.0, z / 23.0 + 3.0)
    if s <= 1:                                                              # ledges hold snow further down
        fuzz += (8.0 if s == 0 else 3.0) * mix * (0.6 + 0.4 * n(x / 5.0 + 3.0, z / 5.0 + 9.0))
    fuzz = max(-3.9, min(LEDGE_SNOW, fuzz))
    a = y + fuzz - snowline
    if a < 0:
        return None
    up = a / max(1.0, peak_y - snowline)                                    # 0 at the snowline, 1 on the top
    lim = 1 if a < 3 else (2 if a < 9 else 3)                              # high up snow sits on every step top
    if s > lim:
        return "crag"
    blot = n(x / 6.0 + 31.0, z / 6.0 + 17.0)
    if streak > 0.62 - 0.32 * mix * (0.5 + 0.5 * s) + 0.15 * up:            # ribs of rock down the faces
        return "crag"
    if blot > 0.66 - 0.55 * mix + 0.15 * up - 0.08 * s:                     # blotches where the wind took the snow
        return "crag"
    return "snow"


def generate(w, l, kind="mountain", height=60, seed=0, base=2, snowline=None, trees=True, boulders=True,
             river=None, solid=None, shell=10, ruggedness=None, ledges=None, snow_mix=None):
    """Blocks {(x, y, z): state} with (0, 0, 0) at the box corner, and an info dict.

    kind: mountain (one massif), range (a ridge along the long side), valley (two ridges with a river), hills (rolling).
    height: rise of the highest ground above `base`. snowline: y where snow starts (default 72% of the height for
    mountains, none for hills; pass a number or False). solid: fill to y=0 (default when the box is up to 160 x 160),
    else a rock shell `shell` blocks thick under the surface.
    ruggedness (0..1, default 0.6): several summits, blunt top, crags, slopes that change steepness.
    ledges (0..1, default 0.6): irregular benches and shoulders on some slopes (never even terraces).
    snow_mix (0..1, default 0.6): snow on ledges and gentle ground above a fuzzy snowline, dark rock on steep faces and
    in streaks and patches; 0 = a clean white cap."""
    if w < 8 or l < 8 or height < 4:
        raise ValueError("terrain needs at least 8 x 8 and a height of 4")
    rug = RUGGED if ruggedness is None else max(0.0, min(1.0, float(ruggedness)))
    led = LEDGES if ledges is None else max(0.0, min(1.0, float(ledges)))
    mix = SNOW_MIX if snow_mix is None else max(0.0, min(1.0, float(snow_mix)))
    h, river_cells, water_y, cliff = heightmap(w, l, kind, height, seed, base, river, rug, led)
    top = [[int(round(v)) for v in row] for row in h]
    if snowline is None:
        snowline = None if kind == "hills" else int(base + (0.72 - 0.25 * mix) * height)
    elif snowline is False:
        snowline = None
    treeline = (snowline - 6 - int(6 * mix)) if snowline else base + int(0.85 * height)
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
    streak = _streaks(top, w, l, kind, Noise(seed + 707)) if mix > 0 else None
    peak_y = max(max(row) for row in top)
    surface = {}
    for z in range(l):
        for x in range(w):
            y, s = top[z][x], sl[z][x]
            jitter = 3.0 * n(x / 9.0, z / 9.0)
            patch = n(x / 13.0 + 50, z / 13.0 + 50)
            if (x, z) in river_cells:
                kind_top = "bed"
            elif snowline and mix > 0 and y + LEDGE_SNOW >= snowline:
                kind_top = _snow_or_rock(x, z, y, s, snowline, peak_y, mix, streak[z][x], n)
                if kind_top is None:
                    kind_top = "crag" if s >= 3 else ("alpine" if y > treeline + jitter else "grass")
            elif snowline and not mix and y + jitter >= snowline:
                kind_top = "snow" if s <= 2 else "rock"
            elif mix and snowline and y > treeline + jitter:                    # alpine: rock, scree and turf mixed
                blot = n(x / 7.0 + 23.0, z / 7.0 + 61.0)
                if s >= 3 or (s == 2 and blot > 0.05) or blot > 0.62 - 0.3 * mix or streak[z][x] > 0.55:
                    kind_top = "crag" if y > (treeline + snowline) / 2 + jitter else "rock"
                elif s == 2 or patch > 0.45:
                    kind_top = "scree"
                else:
                    kind_top = "alpine"
            elif s >= 3:
                kind_top = "crag" if mix and y > treeline - 4 + jitter and streak[z][x] > 0.2 else "rock"
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
                    st = SNOW if d == 0 else (_dark(x, yy, z, n) if mix and d <= 3 else _rock(x, yy, z, n))
                elif kind_top == "crag":
                    st = _dark(x, yy, z, n) if d <= 4 else _rock(x, yy, z, n)
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
            "solid": solid, "blocks": len(blocks), "seed": seed, "ruggedness": rug, "ledges": led, "snow_mix": mix}
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
