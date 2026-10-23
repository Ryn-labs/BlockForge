"""The building toolkit Claude's scripts run against. Every function here is available as a global
inside a build script. Coordinates: x = east, y = up, z = south. Any integer coords are fine; the
finished build is shifted so its lowest corner is (0, 0, 0)."""
import math
import random as _random

MAX_BLOCKS = 3_000_000
MAX_SPAN = 400

_blocks = {}
_tiles = {}           # (x, y, z) -> container contents, e.g. {"id": "minecraft:hopper", "items": [...], "name": "..."}
_modules = []         # proven machines placed by modules.py (locked: the runner rejects scripts that build over them)
_entities = []        # mobs in the build: [x, y, z, {"id": ..., ...}] (see testkit.py)
_tests = []           # in-game test steps for the test lab (see testkit.py)
_meta = {"name": None, "description": None}
random = _random.Random(1337)


class BuildError(Exception):
    pass


def _norm(st):
    if st is None:
        return None
    st = str(st).strip().lower().replace(" ", "")
    if not st or st in ("air", "minecraft:air", "cave_air", "minecraft:cave_air"):
        return None
    if ":" not in st.split("[", 1)[0]:
        st = "minecraft:" + st
    return st


def B(block, **props):
    """Block state string, e.g. B('oak_stairs', facing='east', half='top')."""
    st = _norm(block) or "minecraft:air"
    if props:
        name, cur = st.split("[", 1)[0], {}
        if "[" in st:
            for kv in st[st.index("[") + 1:-1].split(","):
                k, v = kv.split("=")
                cur[k] = v
        for k, v in props.items():
            cur[k] = str(v).lower() if isinstance(v, bool) else str(v)
        st = name + "[" + ",".join(f"{k}={v}" for k, v in sorted(cur.items())) + "]"
    return st


def name(text, description=None):
    """Name the build (shown in the gallery)."""
    _meta["name"] = str(text)[:80]
    if description:
        _meta["description"] = str(description)[:400]


def block(x, y, z, st):
    """Place one block (use 'air' or None to remove)."""
    p = (int(round(x)), int(round(y)), int(round(z)))
    st = _norm(st)
    if st is None:
        _blocks.pop(p, None)
        return
    if len(_blocks) >= MAX_BLOCKS and p not in _blocks:
        raise BuildError(f"build is over {MAX_BLOCKS} blocks")
    _blocks[p] = st


setblock = place = block


def get(x, y, z):
    """Block state at a position, or None for air."""
    return _blocks.get((int(round(x)), int(round(y)), int(round(z))))


def is_air(x, y, z):
    return get(x, y, z) is None


def _rng(a, b):
    a, b = int(round(a)), int(round(b))
    return range(min(a, b), max(a, b) + 1)


def fill(x1, y1, z1, x2, y2, z2, st, hollow=False, outline=False, only_air=False):
    """Fill a box (inclusive). hollow=True keeps the shell and clears the inside;
    outline=True keeps the shell and leaves the inside alone; only_air=True never overwrites."""
    st = _norm(st)
    xs, ys, zs = _rng(x1, x2), _rng(y1, y2), _rng(z1, z2)
    for x in xs:
        for y in ys:
            for z in zs:
                edge = x in (xs[0], xs[-1]) or y in (ys[0], ys[-1]) or z in (zs[0], zs[-1])
                if (hollow or outline) and not edge:
                    if hollow:
                        _blocks.pop((x, y, z), None)
                    continue
                if only_air and (x, y, z) in _blocks:
                    continue
                block(x, y, z, st)


def clear(x1, y1, z1, x2, y2, z2):
    fill(x1, y1, z1, x2, y2, z2, None)


def walls(x1, y1, z1, x2, y2, z2, st):
    """Four vertical walls of a box (no floor or ceiling)."""
    xs, zs = _rng(x1, x2), _rng(z1, z2)
    for y in _rng(y1, y2):
        for x in xs:
            block(x, y, zs[0], st)
            block(x, y, zs[-1], st)
        for z in zs:
            block(xs[0], y, z, st)
            block(xs[-1], y, z, st)


def floor(x1, z1, x2, z2, y, st):
    fill(x1, y, z1, x2, y, z2, st)


def replace(x1, y1, z1, x2, y2, z2, old, new):
    """Replace blocks whose name (without properties) matches old (or a list of names)."""
    olds = [old] if isinstance(old, str) else list(old)
    olds = {_norm(o).split("[", 1)[0] for o in olds}
    for x in _rng(x1, x2):
        for y in _rng(y1, y2):
            for z in _rng(z1, z2):
                cur = _blocks.get((x, y, z))
                if cur and cur.split("[", 1)[0] in olds:
                    block(x, y, z, new)


def line(x1, y1, z1, x2, y2, z2, st, width=1):
    """Straight line between two points (width>1 makes it a thick round line)."""
    n = int(max(abs(x2 - x1), abs(y2 - y1), abs(z2 - z1))) or 1
    r = (width - 1) / 2
    for i in range(n + 1):
        t = i / n
        cx, cy, cz = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, z1 + (z2 - z1) * t
        if width <= 1:
            block(cx, cy, cz, st)
        else:
            sphere(cx, cy, cz, r + 0.3, st)


def sphere(cx, cy, cz, r, st, hollow=False, thickness=1.0):
    ellipsoid(cx, cy, cz, r, r, r, st, hollow, thickness)


def ellipsoid(cx, cy, cz, rx, ry, rz, st, hollow=False, thickness=1.0, y_min=None, y_max=None):
    """Solid or hollow ellipsoid. y_min/y_max clip it (e.g. y_min=cy for a dome)."""
    for x in range(math.floor(cx - rx), math.ceil(cx + rx) + 1):
        for y in range(math.floor(cy - ry), math.ceil(cy + ry) + 1):
            if (y_min is not None and y < y_min) or (y_max is not None and y > y_max):
                continue
            for z in range(math.floor(cz - rz), math.ceil(cz + rz) + 1):
                d = ((x - cx) / (rx + .5)) ** 2 + ((y - cy) / (ry + .5)) ** 2 + ((z - cz) / (rz + .5)) ** 2
                if d > 1:
                    continue
                if hollow:
                    ix = ((x - cx) / max(rx + .5 - thickness, .01)) ** 2 + ((y - cy) / max(ry + .5 - thickness, .01)) ** 2 \
                        + ((z - cz) / max(rz + .5 - thickness, .01)) ** 2
                    if ix <= 1:
                        continue
                block(x, y, z, st)


def dome(cx, cy, cz, r, st, hollow=True):
    ellipsoid(cx, cy, cz, r, r, r, st, hollow, y_min=cy)


def cylinder(cx, y, cz, r, h, st, hollow=False, axis="y", thickness=1.0):
    """Cylinder of radius r and height h starting at y (axis='x'/'z' lays it on its side:
    then (cx, y, cz) is the centre of the starting face and h runs along +axis)."""
    R = r + 0.5
    for a in range(-math.ceil(r) - 1, math.ceil(r) + 2):
        for b in range(-math.ceil(r) - 1, math.ceil(r) + 2):
            d = math.hypot(a, b)
            if d > R or (hollow and d <= R - thickness):
                continue
            for k in range(int(h)):
                if axis == "y":
                    block(cx + a, y + k, cz + b, st)
                elif axis == "x":
                    block(cx + k, y + a, cz + b, st)
                else:
                    block(cx + a, y + b, cz + k, st)


def circle(cx, y, cz, r, st, filled=False):
    cylinder(cx, y, cz, r, 1, st, hollow=not filled)


def cone(cx, y, cz, r, h, st, hollow=False):
    """Cone with base radius r at y and tip at y+h-1."""
    for k in range(int(h)):
        rr = r * (1 - k / max(h, 1))
        cylinder(cx, y + k, cz, max(rr, 0), 1, st, hollow=hollow and k < h - 1)


def pyramid(x1, z1, x2, z2, y, st, hollow=False):
    """Stepped pyramid over a rectangle, starting at y."""
    x1, x2 = sorted((int(x1), int(x2)))
    z1, z2 = sorted((int(z1), int(z2)))
    k = 0
    while x1 + k <= x2 - k and z1 + k <= z2 - k:
        if hollow:
            walls(x1 + k, y + k, z1 + k, x2 - k, y + k, z2 - k, st)
        else:
            fill(x1 + k, y + k, z1 + k, x2 - k, y + k, z2 - k, st)
        k += 1
    return y + k - 1


def gable_roof(x1, z1, x2, z2, y, stairs, fill_block=None, ridge="x", overhang=1, slab=None):
    """Stair gable roof over the rectangle (x1,z1)-(x2,z2) whose eaves sit at y.
    ridge='x' runs the ridge east-west (slopes face north/south); ridge='z' runs it north-south.
    fill_block fills the triangular gable ends; slab caps an odd-width ridge."""
    x1, x2 = sorted((int(x1), int(x2)))
    z1, z2 = sorted((int(z1), int(z2)))
    o = overhang
    if ridge == "x":
        a, b = z1 - o, z2 + o
        k = 0
        while a + k <= b - k:
            yy = y + k
            for x in range(x1 - o, x2 + o + 1):
                if a + k == b - k:
                    block(x, yy, a + k, slab or B(stairs, facing="south"))
                else:
                    block(x, yy, a + k, B(stairs, facing="south"))
                    block(x, yy, b - k, B(stairs, facing="north"))
            if fill_block:
                for z in range(max(a + k + 1, z1), min(b - k - 1, z2) + 1):
                    block(x1, yy, z, fill_block)
                    block(x2, yy, z, fill_block)
            k += 1
    else:
        a, b = x1 - o, x2 + o
        k = 0
        while a + k <= b - k:
            yy = y + k
            for z in range(z1 - o, z2 + o + 1):
                if a + k == b - k:
                    block(a + k, yy, z, slab or B(stairs, facing="east"))
                else:
                    block(a + k, yy, z, B(stairs, facing="east"))
                    block(b - k, yy, z, B(stairs, facing="west"))
            if fill_block:
                for x in range(max(a + k + 1, x1), min(b - k - 1, x2) + 1):
                    block(x, yy, z1, fill_block)
                    block(x, yy, z2, fill_block)
            k += 1


def hip_roof(x1, z1, x2, z2, y, stairs, overhang=1, top=None):
    """Four-sided stair roof (eaves at y)."""
    x1, x2 = sorted((int(x1), int(x2)))
    z1, z2 = sorted((int(z1), int(z2)))
    ax, bx, az, bz = x1 - overhang, x2 + overhang, z1 - overhang, z2 + overhang
    k = 0
    while ax + k <= bx - k and az + k <= bz - k:
        yy = y + k
        lo_x, hi_x, lo_z, hi_z = ax + k, bx - k, az + k, bz - k
        if lo_x == hi_x or lo_z == hi_z:
            fill(lo_x, yy, lo_z, hi_x, yy, hi_z, top or B(stairs.replace("_stairs", "_slab")))
            break
        for x in range(lo_x, hi_x + 1):
            block(x, yy, lo_z, B(stairs, facing="south"))
            block(x, yy, hi_z, B(stairs, facing="north"))
        for z in range(lo_z + 1, hi_z):
            block(lo_x, yy, z, B(stairs, facing="east"))
            block(hi_x, yy, z, B(stairs, facing="west"))
        k += 1


_FLIP_X = {"east": "west", "west": "east"}
_FLIP_Z = {"north": "south", "south": "north"}


def _flip(st, table):
    if "[" not in st:
        return st
    out = st
    for k in ("facing", "rotation_dir"):
        for a, b in table.items():
            if f"{k}={a}" in out:
                return out.replace(f"{k}={a}", f"{k}={b}")
    return out


def mirror(axis="x", center=0.0, x1=None, x2=None):
    """Copy every block across the plane axis=center (e.g. mirror('x', 15.5) mirrors west half to east),
    flipping stair/door facings. Existing blocks on the far side are overwritten."""
    items = list(_blocks.items())
    for (x, y, z), st in items:
        if axis == "x":
            block(round(2 * center - x), y, z, _flip(st, _FLIP_X))
        else:
            block(x, y, round(2 * center - z), _flip(st, _FLIP_Z))


def copy(x1, y1, z1, x2, y2, z2, dx, dy, dz):
    """Copy a region by an offset."""
    src = [((x, y, z), _blocks[(x, y, z)]) for x in _rng(x1, x2) for y in _rng(y1, y2) for z in _rng(z1, z2)
           if (x, y, z) in _blocks]
    for (x, y, z), st in src:
        block(x + dx, y + dy, z + dz, st)


def tree(x, y, z, kind="oak", height=None):
    """Simple decorative tree (kind: oak, birch, spruce, dark_oak, jungle, acacia, cherry, mangrove)."""
    h = height or random.randint(5, 7)
    log, leaves = B(f"{kind}_log", axis="y"), B(f"{kind}_leaves", persistent="true")
    if kind == "spruce":
        h = height or random.randint(7, 10)
        for k in range(h):
            block(x, y + k, z, log)
        for k in range(2, h):
            r = 1 + (h - k) // 3 if k % 2 == 0 else (h - k) // 3
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    if abs(a) + abs(b) <= r + (r > 1) and (a or b):
                        block(x + a, y + k, z + b, leaves)
        block(x, y + h, z, leaves)
        block(x, y + h + 1, z, leaves)
        return
    ellipsoid(x, y + h - 1, z, 2.5, 2, 2.5, leaves)
    for k in range(h):
        block(x, y + k, z, log)


def noise(x, z, scale=8.0, seed=0):
    """Smooth 0..1 value noise for terrain and texture variation."""
    def h(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 2147483647) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return (n ^ (n >> 16)) / 0xFFFFFFFF
    fx, fz = x / scale, z / scale
    i, j = math.floor(fx), math.floor(fz)
    tx, tz = fx - i, fz - j
    sx, sz = tx * tx * (3 - 2 * tx), tz * tz * (3 - 2 * tz)
    a = h(i, j) + (h(i + 1, j) - h(i, j)) * sx
    b = h(i, j + 1) + (h(i + 1, j + 1) - h(i, j + 1)) * sx
    return a + (b - a) * sz


def pick(*options, weights=None):
    """Random choice - handy for texture: pick('stone_bricks', 'cracked_stone_bricks', weights=[4, 1])."""
    return random.choices(options, weights=weights)[0]


def bounds():
    """(min_x, min_y, min_z, max_x, max_y, max_z) of what has been built so far."""
    if not _blocks:
        return (0, 0, 0, 0, 0, 0)
    xs, ys, zs = zip(*_blocks)
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def count():
    return len(_blocks)


EXPORTS = [
    "B", "name", "block", "setblock", "place", "get", "is_air", "fill", "clear", "walls", "floor", "replace",
    "line", "sphere", "ellipsoid", "dome", "cylinder", "circle", "cone", "pyramid", "gable_roof", "hip_roof",
    "mirror", "copy", "tree", "noise", "pick", "bounds", "count", "random", "math",
]

# ------------------------------------------------------------------ redstone (see redstone.py)
from . import redstone as _redstone  # noqa: E402

_redstone.bind(_blocks, block)
for _n in _redstone.EXPORTS:
    globals()[_n] = getattr(_redstone, _n)
EXPORTS += _redstone.EXPORTS

# ------------------------------------------------------------------ proven machines (see modules.py)
from . import modules as _modules_lib  # noqa: E402

_modules_lib.bind(_blocks, _tiles, _modules, block, BuildError)
for _n in _modules_lib.EXPORTS:
    globals()[_n] = getattr(_modules_lib, _n)
EXPORTS += _modules_lib.EXPORTS

# ------------------------------------------------------------------ mobs + in-game tests (see testkit.py)
from . import testkit as _testkit  # noqa: E402

_testkit.bind(_entities, _tests, BuildError)
for _n in _testkit.EXPORTS:
    globals()[_n] = getattr(_testkit, _n)
EXPORTS += _testkit.EXPORTS
