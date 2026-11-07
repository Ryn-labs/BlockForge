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


def _normalise(blocks, tiles, ents=None):
    """Shift so the lowest corner is 0,0,0 (mobs move with the blocks). Returns 2 values, or 3 when `ents` is given."""
    if not blocks:
        return (blocks, tiles) if ents is None else (blocks, tiles, ents)
    mx = min(p[0] for p in blocks); my = min(p[1] for p in blocks); mz = min(p[2] for p in blocks)
    b = {(x - mx, y - my, z - mz): s for (x, y, z), s in blocks.items()}
    t = {(x - mx, y - my, z - mz): v for (x, y, z), v in tiles.items()}
    if ents is None:
        return b, t
    return b, t, [[ex - mx, ey - my, ez - mz, e] for ex, ey, ez, e in ents]


def rotate(blocks, tiles, turns=1, ents=None):
    """Turn the build clockwise (seen from above) by 90 degrees x turns."""
    turns %= 4
    for _ in range(turns):
        blocks = {(-z, y, x): _transform_state(s, _CW, rot16=lambda r: r + 4) for (x, y, z), s in blocks.items()}
        tiles = {(-z, y, x): t for (x, y, z), t in tiles.items()}
        if ents is not None:
            ents = [[1 - ez, ey, ex, e] for ex, ey, ez, e in ents]
    return _normalise(blocks, tiles, ents)


def mirror(blocks, tiles, axis="x", ents=None):
    """axis='x' flips east<->west (left-right), axis='z' flips north<->south (front-back)."""
    if axis == "x":
        f, r = _FLIP_X, (lambda v: 16 - v)
        b = {(-x, y, z): _transform_state(s, f, mirror=True, rot16=r) for (x, y, z), s in blocks.items()}
        t = {(-x, y, z): v for (x, y, z), v in tiles.items()}
        ents = None if ents is None else [[1 - ex, ey, ez, e] for ex, ey, ez, e in ents]
    else:
        f, r = _FLIP_Z, (lambda v: 8 - v)
        b = {(x, y, -z): _transform_state(s, f, mirror=True, rot16=r) for (x, y, z), s in blocks.items()}
        t = {(x, y, -z): v for (x, y, z), v in tiles.items()}
        ents = None if ents is None else [[ex, ey, 1 - ez, e] for ex, ey, ez, e in ents]
    return _normalise(b, t, ents)


def cut(blocks, tiles, y_min=None, y_max=None, ents=None):
    """Keep only layers y_min..y_max (inclusive)."""
    lo = -10 ** 9 if y_min is None else int(y_min)
    hi = 10 ** 9 if y_max is None else int(y_max)
    b = {p: s for p, s in blocks.items() if lo <= p[1] <= hi}
    t = {p: v for p, v in tiles.items() if p in b}
    if not b:
        raise ValueError("That would remove every block.")
    if ents is not None:
        ents = [x for x in ents if lo <= int(x[1] // 1) <= hi]
    return _normalise(b, t, ents)


MAX_BLOCKS = 5_000_000
_FIRST_ONLY = re.compile(r"(_door$|_bed$|^(tall_grass|large_fern|sunflower|lilac|rose_bush|peony|pitcher_plant|tall_seagrass)$|"
                         r"torch|lantern|chest|barrel|furnace|smoker|hopper|dropper|dispenser|shulker_box|_sign$|_hanging_sign$|_banner$|_button$|^lever$|candle|_head$|_skull$|flower_pot|"
                         r"^(short_grass|fern|dandelion|poppy|blue_orchid|allium|azure_bluet|oxeye_daisy|cornflower|"
                         r"lily_of_the_valley|[a-z]+_tulip|[a-z_]+_sapling|bamboo|sugar_cane|kelp)$)")
_DETAIL = re.compile(r"(_door$|_trapdoor$|glass|_pane$|iron_bars|ladder|torch|lantern|chest|barrel|furnace|_bed$|_sign$|"
                     r"_banner$|_button$|^lever$|candle|crafting_table|bookshelf|^(anvil|cauldron|brewing_stand|enchanting_table)$)")


def rescale(blocks, tiles, new_size, ents=None):
    """Stretch or shrink the whole build to (W, H, L) blocks (nearest-neighbour, no AI).
    Growing repeats blocks; shrinking keeps a solid block wherever any block was in that spot, so walls stay closed.
    Two-part blocks (doors, beds, tall plants) are kept once and their other half is added afterwards."""
    if not blocks:
        raise ValueError("The build is empty.")
    mx = max(p[0] for p in blocks) + 1; my = max(p[1] for p in blocks) + 1; mz = max(p[2] for p in blocks) + 1
    nw, nh, nl = (max(1, int(v)) for v in new_size)
    sx, sy, sz = nw / mx, nh / my, nl / mz
    if abs(sx - 1) < 1e-9 and abs(sy - 1) < 1e-9 and abs(sz - 1) < 1e-9:
        raise ValueError("That is the size it already is.")
    if len(blocks) * max(sx, 1) * max(sy, 1) * max(sz, 1) > MAX_BLOCKS * 1.2 or nw * nh * nl > 400 ** 3 * 4:
        raise ValueError(f"That would be more than {MAX_BLOCKS:,} blocks. Pick a smaller size.")

    def span(v, s):
        if s >= 1:
            a, b = round(v * s), round((v + 1) * s)
            return range(a, max(a + 1, b))
        return (int(v * s),)                                 # shrinking: several source blocks vote for one target spot

    votes, first = {}, {}
    for (x, y, z), st in blocks.items():
        name, props = parse_state(st)
        bare = name.replace("minecraft:", "")
        multi = bool(_FIRST_ONLY.search(bare)) or (x, y, z) in tiles       # one of each: never a 2x2x2 pile of chests
        if multi and (props.get("half") == "upper" or props.get("part") == "head"):
            continue                                         # the other half is added after scaling
        weight = 100 if _DETAIL.search(bare) else 1          # when shrinking, doors and windows beat plain wall
        xs, ys, zs = span(x, sx), span(y, sy), span(z, sz)
        for tx in xs:
            for ty in ys:
                for tz in zs:
                    if multi and not (tx == xs[0] and ty == ys[0] and tz == zs[0]):
                        continue
                    v = votes.setdefault((tx, ty, tz), {})
                    v[st] = v.get(st, 0) + weight
                    if (x, y, z) in tiles and (tx, ty, tz) not in first:
                        first[(tx, ty, tz)] = (x, y, z)
    out = {p: max(v.items(), key=lambda kv: kv[1])[0] for p, v in votes.items()}
    t_out = {}
    for tp, sp in first.items():
        tile = tiles.get(sp)
        if tile and out.get(tp, "").split("[", 1)[0] == tile.get("id"):
            t_out[tp] = tile
    e_out = None if ents is None else [[ex * sx, ey * sy, ez * sz, e] for ex, ey, ez, e in ents]
    return _normalise(out, t_out, e_out)


_STATE_OK = re.compile(r"^[a-z0-9_.:-]+$")


def check_name(name):
    n = str(name or "").strip().lower().replace(" ", "_")
    if not n or not _STATE_OK.match(n.split("[", 1)[0]):
        raise ValueError("Pick a real block name, e.g. spruce_planks")
    return n
