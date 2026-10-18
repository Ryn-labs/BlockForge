"""Redstone for build scripts: helpers that get block states right, an auto-wiring pass (WorldEdit and
Litematica paste blocks exactly as saved, so dust and rails must already be connected), and a checker that
reports problems back to the AI.

Direction words everywhere: 'north' (-z), 'south' (+z), 'east' (+x), 'west' (-x), 'up', 'down'."""

DIRS = {"north": (0, 0, -1), "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}
HORIZ = ("north", "south", "east", "west")
OPP = {"north": "south", "south": "north", "east": "west", "west": "east", "up": "down", "down": "up"}

_blocks = None          # set by bind(): the build's {(x, y, z): state} dict
_place = None           # buildkit.block
_fixed_rails = set()    # rails whose shape the script chose itself


def bind(blocks, place):
    global _blocks, _place
    _blocks, _place = blocks, place


def _dir(d, allow_vertical=False):
    d = str(d).lower().strip()
    d = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down", "+z": "south", "-z": "north",
         "+x": "east", "-x": "west", "+y": "up", "-y": "down"}.get(d, d)
    ok = DIRS if allow_vertical else HORIZ
    if d not in ok:
        raise ValueError(f"direction must be one of {', '.join(ok)} (got {d!r})")
    return d


def _st(name, **props):
    return "minecraft:" + name + ("[" + ",".join(f"{k}={v}" for k, v in sorted(props.items())) + "]" if props else "")


# ------------------------------------------------------------------ helpers (exported to scripts)
def dust(x, y, z):
    """Redstone dust. Connections are worked out automatically when the build is saved."""
    _place(x, y, z, _st("redstone_wire", north="none", south="none", east="none", west="none", power=0))


def dust_line(x1, z1, x2, z2, y):
    """Dust from (x1, z1) to (x2, z2) at height y: along x first, then along z (an L shape)."""
    step = 1 if x2 >= x1 else -1
    for x in range(int(x1), int(x2) + step, step):
        dust(x, y, z1)
    step = 1 if z2 >= z1 else -1
    for z in range(int(z1), int(z2) + step, step):
        dust(x2, y, z)


def repeater(x, y, z, toward, delay=1, locked=False):
    """Repeater sending power TOWARD a direction (e.g. toward='north' outputs into the block north of it)."""
    t = _dir(toward)
    _place(x, y, z, _st("repeater", facing=OPP[t], delay=max(1, min(4, int(delay))), locked=str(bool(locked)).lower(),
                        powered="false"))


def comparator(x, y, z, toward, subtract=False):
    """Comparator outputting TOWARD a direction. subtract=True for subtract mode."""
    t = _dir(toward)
    _place(x, y, z, _st("comparator", facing=OPP[t], mode="subtract" if subtract else "compare", powered="false"))


def redstone_torch(x, y, z, attach="floor", lit=True):
    """Redstone torch standing on the block below (attach='floor') or on the side of the block in direction
    `attach` (attach='north' = stuck to the block north of it)."""
    if str(attach).lower() in ("floor", "down", "ground"):
        _place(x, y, z, _st("redstone_torch", lit=str(bool(lit)).lower()))
    else:
        a = _dir(attach)
        _place(x, y, z, _st("redstone_wall_torch", facing=OPP[a], lit=str(bool(lit)).lower()))


def _switch(name, x, y, z, attach, facing, extra):
    att = str(attach).lower()
    if att in ("floor", "down", "ground"):
        _place(x, y, z, _st(name, face="floor", facing=_dir(facing), **extra))
    elif att in ("ceiling", "up", "top"):
        _place(x, y, z, _st(name, face="ceiling", facing=_dir(facing), **extra))
    else:
        a = _dir(att)
        _place(x, y, z, _st(name, face="wall", facing=OPP[a], **extra))


def lever(x, y, z, attach="floor", facing="north", on=False):
    """Lever on the floor/ceiling, or on the side of the block in direction `attach`."""
    _switch("lever", x, y, z, attach, facing, {"powered": str(bool(on)).lower()})


def button(x, y, z, attach="floor", facing="north", kind="stone"):
    """Button (kind: stone, oak, spruce, polished_blackstone, ...) on floor/ceiling or a wall."""
    _switch(f"{kind}_button", x, y, z, attach, facing, {"powered": "false"})


def pressure_plate(x, y, z, kind="stone"):
    """kind: stone, oak, ..., light_weighted, heavy_weighted."""
    name = f"{kind}_pressure_plate"
    _place(x, y, z, _st(name, power=0) if "weighted" in kind else _st(name, powered="false"))


def piston(x, y, z, push, sticky=False):
    """Piston whose head pushes in direction `push` (any of the 6 directions)."""
    _place(x, y, z, _st("sticky_piston" if sticky else "piston", facing=_dir(push, True), extended="false"))


def observer(x, y, z, watch):
    """Observer whose face WATCHES direction `watch`; it pulses out of the opposite side."""
    _place(x, y, z, _st("observer", facing=_dir(watch, True), powered="false"))


def hopper(x, y, z, into="down"):
    """Hopper feeding items INTO the block in that direction ('down' or a side)."""
    d = _dir(into, True)
    if d == "up":
        raise ValueError("hoppers can't point up")
    _place(x, y, z, _st("hopper", facing=d, enabled="true"))


def dropper(x, y, z, out):
    _place(x, y, z, _st("dropper", facing=_dir(out, True), triggered="false"))


def dispenser(x, y, z, out):
    _place(x, y, z, _st("dispenser", facing=_dir(out, True), triggered="false"))


def lamp(x, y, z):
    _place(x, y, z, _st("redstone_lamp", lit="false"))


def rail(x, y, z, kind="rail", shape=None):
    """Rail (kind: rail, powered, detector, activator). The shape is worked out from neighbouring rails unless
    you give one (north_south, east_west, ascending_north, ..., and for plain rails north_east etc.)."""
    name = {"rail": "rail", "powered": "powered_rail", "detector": "detector_rail", "activator": "activator_rail"}[kind]
    props = {"shape": shape or "north_south"}
    if name != "rail":
        props["powered"] = "false"
    _place(x, y, z, _st(name, **props))
    p = (int(round(x)), int(round(y)), int(round(z)))
    (_fixed_rails.add if shape else _fixed_rails.discard)(p)


EXPORTS = ["dust", "dust_line", "repeater", "comparator", "redstone_torch", "lever", "button", "pressure_plate",
           "piston", "observer", "hopper", "dropper", "dispenser", "lamp", "rail"]


# ------------------------------------------------------------------ block classification
def _name(st):
    return st.split("[", 1)[0].replace("minecraft:", "") if st else None


def _props(st):
    if not st or "[" not in st:
        return {}
    return dict(kv.split("=", 1) for kv in st[st.index("[") + 1:-1].split(","))


def _with(st, **kw):
    p = _props(st)
    p.update(kw)
    return "minecraft:" + _name(st) + ("[" + ",".join(f"{k}={v}" for k, v in sorted(p.items())) + "]" if p else "")


NOT_SOLID = ("air", "glass", "pane", "leaves", "slab", "stairs", "fence", "_wall", "carpet", "torch", "redstone_wire",
             "repeater", "comparator", "lever", "button", "pressure_plate", "rail", "door", "trapdoor", "sign",
             "banner", "lantern", "chain", "bars", "water", "lava", "ladder", "vine", "flower", "sapling", "grass",
             "fern", "bush", "mushroom", "head", "skull", "candle", "hopper", "piston_head", "scaffolding", "snow",
             "cobweb", "pot", "bell", "campfire", "lily_pad", "kelp", "seagrass", "coral", "dripleaf", "tripwire")
POWER_SOURCES = ("lever", "button", "pressure_plate", "redstone_torch", "redstone_wall_torch", "redstone_block",
                 "observer", "daylight_detector", "target", "trapped_chest", "tripwire_hook", "detector_rail",
                 "lectern", "sculk_sensor", "calibrated_sculk_sensor", "comparator")
REDSTONE_PARTS = ("redstone_wire", "repeater", "comparator", "piston", "sticky_piston", "observer", "redstone_lamp",
                  "dropper", "dispenser", "hopper", "note_block", "powered_rail", "activator_rail") + POWER_SOURCES


def _solid(st):
    n = _name(st)
    if not n:
        return False
    if n.endswith("_slab"):
        return _props(st).get("type") == "double"
    return not any(k in n for k in NOT_SOLID)


def _can_support(st):
    """Can redstone dust / repeaters / rails sit on top of this block?"""
    n = _name(st)
    if not n:
        return False
    if _solid(st) or "glass" in n or n in ("hopper", "observer", "piston", "sticky_piston"):
        return True
    p = _props(st)
    return (n.endswith("_slab") and p.get("type") == "top") or (n.endswith("_stairs") and p.get("half") == "top")


def _add(p, d):
    o = DIRS[d]
    return (p[0] + o[0], p[1] + o[1], p[2] + o[2])


def _connects_dust(st, d):
    """Does dust at p connect sideways to block `st` lying in direction d from it?"""
    n = _name(st)
    if not n:
        return False
    if n == "redstone_wire" or n in ("redstone_torch", "redstone_wall_torch", "redstone_block", "lever", "target",
                                     "daylight_detector", "trapped_chest", "comparator", "detector_rail", "lectern",
                                     "tripwire_hook", "sculk_sensor") or n.endswith(("_button", "_pressure_plate")):
        return True
    p = _props(st)
    if n == "repeater":
        return p.get("facing") in (d, OPP[d])
    if n == "observer":
        return p.get("facing") == d            # its output (back) points at the dust
    return False


# ------------------------------------------------------------------ finalize: wire up dust and rails
def _fix_dust(blocks):
    for p, st in list(blocks.items()):
        if _name(st) != "redstone_wire":
            continue
        above = blocks.get(_add(p, "up"))
        conn = {}
        for d in HORIZ:
            q = _add(p, d)
            nb = blocks.get(q)
            if nb and _connects_dust(nb, d):
                conn[d] = "side"
            elif _name(blocks.get(_add(q, "up"))) == "redstone_wire" and not _solid(above) and _solid(nb):
                conn[d] = "up"
            elif _name(blocks.get(_add(q, "down"))) == "redstone_wire" and not _solid(nb):
                conn[d] = "side"
        if not conn:
            conn = {d: "side" for d in HORIZ}         # an unconnected dot is a "+" in vanilla
        elif len(conn) == 1:
            (d, _), = conn.items()
            conn[OPP[d]] = "side"                     # a single connection draws a straight line
        blocks[p] = _with(st, **{d: conn.get(d, "none") for d in HORIZ})


def _fix_rails(blocks):
    rails = {p for p, st in blocks.items() if (_name(st) or "").endswith("rail") and p not in _fixed_rails}
    is_rail = lambda q: (_name(blocks.get(q)) or "").endswith("rail")
    for p in rails:
        st = blocks[p]
        near = {d for d in HORIZ if is_rail(_add(p, d)) or is_rail(_add(_add(p, d), "down"))}
        up = [d for d in HORIZ if is_rail(_add(_add(p, d), "up"))]
        shape = None
        if up:
            shape = "ascending_" + up[0]
        elif _name(st) == "rail" and len(near) >= 2 and ({"north", "south"} & near) and ({"east", "west"} & near):
            ns = "south" if "south" in near else "north"
            ew = "east" if "east" in near else "west"
            shape = f"{ns}_{ew}"
        elif near & {"east", "west"} and not near & {"north", "south"}:
            shape = "east_west"
        elif near:
            shape = "north_south"
        if shape:
            blocks[p] = _with(st, shape=shape)


def _kind(n):
    if not n:
        return None
    if n.endswith("_fence_gate"):
        return "gate"
    if n.endswith("_fence"):
        return "nether_fence" if n == "nether_brick_fence" else "fence"
    if n.endswith("_pane") or n in ("glass_pane", "iron_bars"):
        return "pane"
    if n.endswith("_wall") and not any(k in n for k in ("torch", "sign", "banner", "head", "skull", "fan", "hanging")):
        return "wall"
    return None


def _fix_connections(blocks):
    """Fences, panes, iron bars and walls: in game these connect on a block update, which pastes don't do."""
    for p, st in list(blocks.items()):
        n = _name(st)
        k = _kind(n)
        if k not in ("fence", "nether_fence", "pane", "wall"):
            continue
        conn = {}
        for d in HORIZ:
            nb = blocks.get(_add(p, d))
            nk = _kind(_name(nb))
            if k in ("fence", "nether_fence"):
                ok = nk == k or nk == "gate" or _solid(nb)
            elif k == "pane":
                ok = nk in ("pane", "wall") or "glass" in (_name(nb) or "") or _solid(nb)
            else:
                ok = nk in ("wall", "pane", "gate") or _solid(nb)
            conn[d] = ok
        if k == "wall":
            straight = (conn["north"] and conn["south"] and not conn["east"] and not conn["west"]) or \
                       (conn["east"] and conn["west"] and not conn["north"] and not conn["south"])
            above = blocks.get(_add(p, "up"))
            up = not straight or _kind(_name(above)) == "wall" or (_name(above) or "").endswith(("torch", "lantern"))
            blocks[p] = _with(st, up=str(up).lower(), **{d: ("low" if conn[d] else "none") for d in HORIZ})
        else:
            blocks[p] = _with(st, **{d: str(conn[d]).lower() for d in HORIZ})


def finalize(blocks):
    """Run after the script. Connects dust, rails, fences, panes and walls, then returns problems found."""
    _fix_dust(blocks)
    _fix_rails(blocks)
    _fix_connections(blocks)
    return check(blocks)


def check(blocks):
    problems, unsupported, floating_wall = [], [], []
    parts = 0
    has_power = False
    loose_dust = 0
    for p, st in blocks.items():
        n = _name(st)
        if n in REDSTONE_PARTS or n.endswith(("_button", "_pressure_plate", "rail")):
            parts += 1
        if n in POWER_SOURCES or n.endswith(("_button", "_pressure_plate")):
            has_power = True
        props = _props(st)
        needs_floor = n in ("redstone_wire", "repeater", "comparator", "redstone_torch") or n.endswith(("rail", "_pressure_plate")) \
            or (n in ("lever",) or n.endswith("_button")) and props.get("face") == "floor"
        if needs_floor and not _can_support(blocks.get(_add(p, "down"))):
            unsupported.append(p)
        if n == "redstone_wall_torch" or ((n == "lever" or n.endswith("_button")) and props.get("face") == "wall"):
            back = OPP.get(props.get("facing", "north"), "south")
            if not blocks.get(_add(p, back)):
                floating_wall.append(p)
        if n == "redstone_wire":
            conns = [props.get(d) for d in HORIZ]
            if conns.count("none") == 0 and not any(blocks.get(_add(p, d)) and _connects_dust(blocks[_add(p, d)], d) for d in HORIZ) \
                    and not any(_name(blocks.get(_add(_add(p, d), v))) == "redstone_wire" for d in HORIZ for v in ("up", "down")):
                loose_dust += 1
    if unsupported:
        problems.append(f"{len(unsupported)} redstone part(s) have nothing solid underneath and would pop off, e.g. at "
                        + ", ".join(map(str, unsupported[:5])))
    if floating_wall:
        problems.append(f"{len(floating_wall)} wall torch/lever/button(s) aren't attached to a block, e.g. at "
                        + ", ".join(map(str, floating_wall[:5])))
    if parts >= 3 and not has_power:
        problems.append("The circuit has no power source (lever, button, pressure plate, redstone torch, redstone block, "
                        "observer, daylight detector...).")
    if loose_dust >= 3:
        problems.append(f"{loose_dust} pieces of redstone dust aren't connected to anything.")
    return problems
