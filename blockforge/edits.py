"""Quick edits that need no AI: swap a block (or a whole family), rotate, mirror, cut layers.

All functions take {(x, y, z): state} and {(x, y, z): tile} and return new dicts. Block states are carried along
correctly: facings turn with the build, stairs/doors/chests swap left and right when mirrored, and so on."""
import re

from .exporters import parse_state, state_str

_CW = {"north": "east", "east": "south", "south": "west", "west": "north"}
_FLIP_X = {"east": "west", "west": "east"}
_FLIP_Z = {"north": "south", "south": "north"}
_SIDES = ("north", "east", "south", "west")
FAMILY_SUFFIXES = ("_planks", "_stairs", "_slab", "_log", "_wood", "_stem", "_hyphae", "_fence_gate", "_fence", "_door",
                   "_trapdoor", "_wall_sign", "_wall_hanging_sign", "_hanging_sign", "_sign", "_button", "_pressure_plate",
                   "_wall", "_leaves", "_sapling", "_bricks", "_brick", "_tiles", "_tile")


def _ns(n):
    return n if ":" in n else "minecraft:" + n


def family_of(name):
    """'minecraft:oak_planks' -> 'minecraft:oak', 'stone_bricks' -> 'minecraft:stone_brick'."""
    n = _ns(name)
    if n.endswith("_bricks"):
        return n[:-1]                                     # stone_bricks -> stone_brick (stone_brick_stairs, _wall...)
    if n.endswith("_tiles"):
        return n[:-1]
    for suf in FAMILY_SUFFIXES:
        if n.endswith(suf):
            return n[: -len(suf)]
    return n


def _shape_kind(name):
    for suf in ("_stairs", "_slab", "_wall", "_fence_gate", "_fence", "_door", "_trapdoor", "_log", "_wood", "_stem",
                "_pane", "_sign", "_button", "_pressure_plate", "_bed", "_carpet", "_candle"):
        if name.endswith(suf):
            return suf
    return None


def swap(blocks, src, dst, family=False, valid=None):
    """Replace block `src` with `dst` everywhere (keeping facing etc. when both are the same kind of block).
    family=True also swaps the related blocks: oak_planks -> spruce_planks turns oak stairs/slabs/fences/logs into spruce.
    valid: optional set of real block names; renamed blocks that don't exist are left alone.
    Returns (new_blocks, swapped_count, skipped_names)."""
    src, dst = _ns(src.split("[", 1)[0]), _ns(dst.split("[", 1)[0])
    sf, df = family_of(src), family_of(dst)
    out, n, skipped = {}, 0, set()
    for p, st in blocks.items():
        name, props = parse_state(st)
        new = None
        if name == src:
            new = dst
        elif family and sf != src and (name.startswith(sf + "_") or name == sf):
            new = df + name[len(sf):]
            if src.endswith("_bricks") and name == sf + "s":
                new = dst
        if new and new != name:
            if valid is not None and new.replace("minecraft:", "") not in valid and new.startswith("minecraft:"):
                skipped.add(name.replace("minecraft:", ""))
                out[p] = st
                continue
            keep = props if _shape_kind(name) == _shape_kind(new) else {}
            out[p] = state_str(new, keep)
            n += 1
        else:
            out[p] = st
    return out, n, sorted(skipped)


# ---------------------------------------------------------------- rotate / mirror
_RAIL_CW = {"north_south": "east_west", "east_west": "north_south", "ascending_north": "ascending_east",
            "ascending_east": "ascending_south", "ascending_south": "ascending_west", "ascending_west": "ascending_north",
            "north_east": "south_east", "south_east": "south_west", "south_west": "north_west", "north_west": "north_east"}


def _turn_dir(d, f):
    return f.get(d, d)


def _turn_rail(shape, f):
    if shape in ("north_south", "east_west"):
        a, b = shape.split("_")
        a, b = f.get(a, a), f.get(b, b)
        return "north_south" if {a, b} == {"north", "south"} else "east_west"
    if shape.startswith("ascending_"):
        return "ascending_" + f.get(shape[10:], shape[10:])
    a, b = shape.split("_")
    a, b = f.get(a, a), f.get(b, b)
    ns = a if a in ("north", "south") else b
    ew = b if ns == a else a
    return f"{ns}_{ew}"


def _transform_state(st, f, mirror=False, rot16=None):
    """f maps horizontal directions; rot16 maps 0..15 sign/banner rotations."""
    name, props = parse_state(st)
    if not props:
        return st
    p = dict(props)
    if "facing" in p:
        p["facing"] = _turn_dir(p["facing"], f)
    if "axis" in p and p["axis"] in ("x", "z") and f.get("east") in ("north", "south"):
        p["axis"] = "z" if p["axis"] == "x" else "x"
    if "rotation" in p and rot16:
        try:
            p["rotation"] = str(rot16(int(p["rotation"])) % 16)
        except ValueError:
            pass
    if "shape" in p and name.endswith("rail"):
        p["shape"] = _turn_rail(p["shape"], f)
    if mirror:
        if "shape" in p and name.endswith("_stairs"):
            p["shape"] = {"inner_left": "inner_right", "inner_right": "inner_left", "outer_left": "outer_right",
                          "outer_right": "outer_left"}.get(p["shape"], p["shape"])
        if "hinge" in p:
            p["hinge"] = "right" if p["hinge"] == "left" else "left"
        if "type" in p and p["type"] in ("left", "right") and name.endswith("chest"):
            p["type"] = "right" if p["type"] == "left" else "left"
    sides = {d: p.pop(d) for d in _SIDES if d in p}
    for d, v in sides.items():
        p[_turn_dir(d, f)] = v
    return state_str(name, p)


def _normalise(blocks, tiles):
    if not blocks:
        return blocks, tiles
    mx = min(p[0] for p in blocks); my = min(p[1] for p in blocks); mz = min(p[2] for p in blocks)
    return ({(x - mx, y - my, z - mz): s for (x, y, z), s in blocks.items()},
            {(x - mx, y - my, z - mz): t for (x, y, z), t in tiles.items()})


def rotate(blocks, tiles, turns=1):
    """Turn the build clockwise (seen from above) by 90 degrees x turns."""
    turns %= 4
    for _ in range(turns):
        blocks = {(-z, y, x): _transform_state(s, _CW, rot16=lambda r: r + 4) for (x, y, z), s in blocks.items()}
        tiles = {(-z, y, x): t for (x, y, z), t in tiles.items()}
    return _normalise(blocks, tiles)


def mirror(blocks, tiles, axis="x"):
    """axis='x' flips east<->west (left-right), axis='z' flips north<->south (front-back)."""
    if axis == "x":
        f, r = _FLIP_X, (lambda v: 16 - v)
        b = {(-x, y, z): _transform_state(s, f, mirror=True, rot16=r) for (x, y, z), s in blocks.items()}
        t = {(-x, y, z): v for (x, y, z), v in tiles.items()}
    else:
        f, r = _FLIP_Z, (lambda v: 8 - v)
        b = {(x, y, -z): _transform_state(s, f, mirror=True, rot16=r) for (x, y, z), s in blocks.items()}
        t = {(x, y, -z): v for (x, y, z), v in tiles.items()}
    return _normalise(b, t)


def cut(blocks, tiles, y_min=None, y_max=None):
    """Keep only layers y_min..y_max (inclusive)."""
    lo = -10 ** 9 if y_min is None else int(y_min)
    hi = 10 ** 9 if y_max is None else int(y_max)
    b = {p: s for p, s in blocks.items() if lo <= p[1] <= hi}
    t = {p: v for p, v in tiles.items() if p in b}
    if not b:
        raise ValueError("That would remove every block.")
    return _normalise(b, t)


_STATE_OK = re.compile(r"^[a-z0-9_.:-]+$")


def check_name(name):
    n = str(name or "").strip().lower().replace(" ", "_")
    if not n or not _STATE_OK.match(n.split("[", 1)[0]):
        raise ValueError("Pick a real block name, e.g. spruce_planks")
    return n
