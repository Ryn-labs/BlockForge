"""Proven building parts as buildkit snippets.

Every function returns a string of build script code (only buildkit functions: block, fill, line, gable_roof, tree, B).
Paste the string into a build_step, or join several. Each pattern passes blockforge/checks.py on its own (no buried path,
no jump steps, no blocked door, nothing floating); tests/test_patterns.py runs all of them through the sandbox.

Coordinates: x east, y up, z south. `dir` / `facing` is north, south, east or west. Positions (x, y, z) are the first
walkable cell or the lowest block of the part; every part also lays a support row at y-1 so it never floats.
"""

DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
OPP = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _dir(name):
    if name not in DIRS:
        raise ValueError(f"direction must be one of north, south, east, west (got {name!r})")
    return DIRS[name]


# Roof colours by name: gable_roof_trim(..., stairs="teal") and the other roofs take these as well as a block name.
ROOF_COLOURS = {"teal": "prismarine_brick_stairs", "green": "oxidized_cut_copper_stairs",
                "copper": "cut_copper_stairs", "gray": "deepslate_tile_stairs", "grey": "deepslate_tile_stairs",
                "red": "red_nether_brick_stairs", "brick": "brick_stairs", "blue": "warped_stairs",
                "dark": "dark_oak_stairs", "brown": "spruce_stairs", "mud": "mud_brick_stairs"}
# Wall styles for framed_house / framed_wall: (fill, frame). "light" is the reference look and the default: a light
# birch fill in an oak log frame. "dark" (spruce in dark oak) only when the user asks for a dark, gothic or spooky build.
WALL_STYLES = {"light": ("birch_planks", "oak_log"), "oak": ("oak_planks", "spruce_log"),
               "stripped": ("stripped_birch_log", "oak_log"), "plaster": ("white_terracotta", "oak_log"),
               "classic": ("oak_planks", "spruce_log"), "dark": ("spruce_planks", "dark_oak_log")}
DEFAULT_STYLE = "light"
# The reference roof: teal slopes with an oak trim (the default of gable_roof_trim, hip_roof_trim, cross_gable_roof).
ROOF_DEFAULT, TRIM_DEFAULT = "teal", "oak"


def _stairs(name):
    name = ROOF_COLOURS.get(str(name), str(name))
    return name if name.endswith("_stairs") else name + "_stairs"


def _full(stairs):
    """The full block of a stair material: oak_stairs -> oak_planks, prismarine_brick_stairs -> prismarine_bricks."""
    base = _stairs(stairs)[:-7]
    if base in WOOD_NAMES:
        return base + "_planks"
    if base.endswith(("_brick", "_tile")) or base == "brick":
        return base + "s"
    return base


def _style(style, fill, frame):
    if style is None:
        style = DEFAULT_STYLE
    if style not in WALL_STYLES:
        raise ValueError(f"style must be one of {', '.join(sorted(WALL_STYLES))} (got {style!r})")
    f, r = WALL_STYLES[style]
    return fill or f, frame or r


def _st(name, **props):
    return "B(%r, %s)" % (name, ", ".join("%s=%r" % kv for kv in props.items()))


def _code(lines):
    return "\n".join(lines) + "\n"


def straight_stair_run(x, y, z, dir, length, width=3, block="stone_brick_stairs", support="stone", path="stone_bricks",
                       landing=2, clear=3):
    """A straight climb: `length` bottom stairs facing uphill, rising 1 per cell from y, then `landing` flat path cells.

    The first stair is at (x, y, z); `width` cells wide to the right-hand side of the direction. Solid support below each
    step down to y-1, and `clear` blocks of air over every step and landing cell (a run cut into a slope is never
    buried under the ground)."""
    dx, dz = _dir(dir)
    px, pz = -dz, dx
    stairs = _stairs(block)
    out = [f"# straight stair run {dir}, {length} steps, width {width}"]
    for i in range(length + max(0, landing)):
        for w in range(width):
            cx, cz = x + dx * i + px * w, z + dz * i + pz * w
            if i < length:
                top = y + i
                out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {top - 1}, {cz}, {support!r})")
                out.append(f"block({cx}, {top}, {cz}, {_st(stairs, facing=dir, half='bottom', shape='straight')})")
            else:
                top = y + length - 1
                out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {top - 1}, {cz}, {support!r})")
                out.append(f"block({cx}, {top}, {cz}, {path!r})")
            if clear:
                out.append(f"clear({cx}, {top + 1}, {cz}, {cx}, {top + max(2, int(clear))}, {cz})")
    return _code(out)


def switchback_landing(x, y, z, dir, length=4, width=2, block="stone_brick_stairs", support="stone", path="stone_bricks"):
    """Two stair runs joined by a flat landing: climb `length` steps along `dir`, turn on the landing, climb `length`
    more back the other way beside the first run (a stone wall separates them). Climbs 2*length blocks in total.
    3 blocks of air are cleared over every step and landing cell."""
    dx, dz = _dir(dir)
    px, pz = -dz, dx
    stairs = _stairs(block)
    L, W = length, width
    depth = max(2, W)
    out = [f"# switchback: {L} steps {dir}, landing, {L} steps back"]

    def cell(off, lat):
        return x + dx * off + px * lat, z + dz * off + pz * lat

    # divider wall between the two runs (support material), then the landing over its end
    for off in range(0, L):
        cx, cz = cell(off, W)
        out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + L - 1}, {cz}, {support!r})")
    for i in range(L):                                              # run A
        for w in range(W):
            cx, cz = cell(i, w)
            out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + i - 1}, {cz}, {support!r})")
            out.append(f"block({cx}, {y + i}, {cz}, {_st(stairs, facing=dir, half='bottom', shape='straight')})")
            out.append(f"clear({cx}, {y + i + 1}, {cz}, {cx}, {y + i + 3}, {cz})")
    for off in range(L, L + depth):                                 # landing, same height as the last stair of run A
        for lat in range(2 * W + 1):
            cx, cz = cell(off, lat)
            out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + L - 2}, {cz}, {support!r})")
            out.append(f"block({cx}, {y + L - 1}, {cz}, {path!r})")
            out.append(f"clear({cx}, {y + L}, {cz}, {cx}, {y + L + 2}, {cz})")
    back = OPP[dir]
    for j in range(L):                                              # run B climbs back toward the start
        for w in range(W):
            cx, cz = cell(L - 1 - j, W + 1 + w)
            out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + L + j - 1}, {cz}, {support!r})")
            out.append(f"block({cx}, {y + L + j}, {cz}, {_st(stairs, facing=back, half='bottom', shape='straight')})")
            out.append(f"clear({cx}, {y + L + j + 1}, {cz}, {cx}, {y + L + j + 3}, {cz})")
    for w in range(W):                                              # exit platform at the top of run B
        cx, cz = cell(-1, W + 1 + w)
        out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + 2 * L - 2}, {cz}, {support!r})")
        out.append(f"block({cx}, {y + 2 * L - 1}, {cz}, {path!r})")
        out.append(f"clear({cx}, {y + 2 * L}, {cz}, {cx}, {y + 2 * L + 2}, {cz})")
    return _code(out)


def lantern_post(x, y, z, style="medieval"):
    """A light on a post standing on a stone foot at y-1. Styles: japanese (stone toro), medieval (fence post with a
    hanging lantern on an arm), nordic, alpine, desert, modern, fantasy; unknown styles use medieval."""
    s = str(style).lower()
    if s == "japanese":
        return _code([
            "# stone toro lantern",
            f"block({x}, {y - 1}, {z}, 'stone_bricks')",
            f"block({x}, {y}, {z}, 'stone_brick_wall')",
            f"block({x}, {y + 1}, {z}, 'stone_brick_wall')",
            f"block({x}, {y + 2}, {z}, 'stone_bricks')",
            f"block({x}, {y + 3}, {z}, {_st('lantern', hanging=False)})",
            f"block({x}, {y + 4}, {z}, {_st('stone_brick_slab', type='bottom')})",
        ])
    post = {"nordic": "spruce_fence", "alpine": "spruce_fence", "desert": "sandstone_wall", "fantasy": "stripped_birch_log",
            "modern": "polished_blackstone_wall"}.get(s, "oak_fence")
    foot = {"desert": "smooth_sandstone", "modern": "polished_andesite"}.get(s, "cobblestone")
    lantern = "soul_lantern" if s in ("nordic", "fantasy") else "lantern"
    top = {"desert": "sandstone_wall", "modern": "polished_blackstone_wall"}.get(s, post)
    lines = [f"# {s} lantern post",
             f"block({x}, {y - 1}, {z}, {foot!r})"]
    if post == "stripped_birch_log":
        lines += [f"block({x}, {y + k}, {z}, {_st(post, axis='y')})" for k in range(3)]
    else:
        lines += [f"block({x}, {y + k}, {z}, {post!r})" for k in range(3)]
    lines += [f"block({x + 1}, {y + 2}, {z}, {top!r})",
              f"block({x + 1}, {y + 1}, {z}, {_st(lantern, hanging=True)})"]
    return _code(lines)


def doorway(x, y, z, facing, wood="oak"):
    """A door in a 3-wide wall piece: log posts and lintel, a two-block door, a floor row at y-1. The door at (x, y, z)
    faces `facing`; the wall runs across it and the cells in front of and behind the door stay clear."""
    dx, dz = _dir(facing)
    px, pz = abs(dz), abs(dx)                                       # the wall runs along the other axis
    log = f"stripped_{wood}_log"
    out = [f"# doorway {facing}",
           f"fill({x - 1}, {y - 1}, {z - 1}, {x + 1}, {y - 1}, {z + 1}, 'stone_bricks')"]
    for s in (-1, 1):
        cx, cz = x + px * s, z + pz * s
        out.append(f"fill({cx}, {y}, {cz}, {cx}, {y + 2}, {cz}, {_st(log, axis='y')})")
    axis = "x" if px else "z"
    out.append(f"block({x}, {y + 2}, {z}, {_st(log, axis=axis)})")
    out.append(f"block({x}, {y}, {z}, {_st(wood + '_door', facing=facing, half='lower', hinge='left', open=False)})")
    out.append(f"block({x}, {y + 1}, {z}, {_st(wood + '_door', facing=facing, half='upper', hinge='left', open=False)})")
    return _code(out)


def window(x, y, z, facing, glass="glass_pane", wall="white_terracotta", frame="oak_planks"):
    """A 1x2 window in a 5-wide wall piece (4 high, floor row at y-1) with a plank frame and an outside sill slab.
    (x, y, z) is the lowest window cell; `facing` is the side the window looks out on."""
    dx, dz = _dir(facing)
    px, pz = abs(dz), abs(dx)
    sides = ("east", "west") if px else ("north", "south")
    out = [f"# window facing {facing}",
           f"fill({x - 2 * px - (1 - px)}, {y - 1}, {z - 2 * pz - (1 - pz)}, {x + 2 * px + (1 - px)}, {y - 1}, "
           f"{z + 2 * pz + (1 - pz)}, 'stone')",
           f"fill({x - 2 * px}, {y}, {z - 2 * pz}, {x + 2 * px}, {y + 3}, {z + 2 * pz}, {wall!r})"]
    for s in (-1, 1):
        cx, cz = x + px * s, z + pz * s
        out.append(f"fill({cx}, {y}, {cz}, {cx}, {y + 3}, {cz}, {frame!r})")
    out.append(f"fill({x}, {y + 3}, {z}, {x}, {y + 3}, {z}, {frame!r})")
    for k in (1, 2):
        out.append(f"block({x}, {y + k}, {z}, {_st(glass, **{sides[0]: True, sides[1]: True})})")
    out.append(f"block({x + dx}, {y}, {z + dz}, {_st(frame.replace('_planks', '_slab'), type='bottom')})")
    return _code(out)


def gable_roof_house_shell(x1, z1, x2, z2, y, h=5, walls="white_terracotta", roof="oak_stairs", wood="oak", door_side="south"):
    """A closed little house: foundation row at y, walls y+1..y+h-1, plank ceiling at y+h, a door in the `door_side`
    wall, two windows, a hanging lantern inside, and a gable roof (ridge along the longer side, overhang 1, gable ends
    filled) from y+h+1. h >= 4 so there are 3 free blocks inside."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    h = max(4, h)
    ridge = "x" if (x2 - x1) >= (z2 - z1) else "z"
    cx, cz = (x1 + x2) // 2, (z1 + z2) // 2
    roof = _stairs(roof)
    out = ["# gable-roof house shell",
           f"fill({x1}, {y}, {z1}, {x2}, {y}, {z2}, 'stone')",
           f"walls({x1}, {y + 1}, {z1}, {x2}, {y + h - 1}, {z2}, {walls!r})",
           f"fill({x1}, {y + h}, {z1}, {x2}, {y + h}, {z2}, {wood + '_planks'!r})"]
    for px_, pz_ in ((x1, z1), (x1, z2), (x2, z1), (x2, z2)):       # corner posts
        out.append(f"fill({px_}, {y + 1}, {pz_}, {px_}, {y + h - 1}, {pz_}, {_st(wood + '_log', axis='y')})")
    door = {"south": (cx, z2), "north": (cx, z1), "east": (x2, cz), "west": (x1, cz)}[door_side]
    out.append(f"block({door[0]}, {y + 1}, {door[1]}, 'air')")
    out.append(f"block({door[0]}, {y + 2}, {door[1]}, 'air')")
    out.append(f"block({door[0]}, {y + 1}, {door[1]}, "
               f"{_st(wood + '_door', facing=door_side, half='lower', hinge='left', open=False)})")
    out.append(f"block({door[0]}, {y + 2}, {door[1]}, "
               f"{_st(wood + '_door', facing=door_side, half='upper', hinge='left', open=False)})")
    wy = [y + 2] if h < 5 else [y + 2, y + 3]
    long_side = ("north", "south") if ridge == "x" else ("east", "west")
    for side in long_side:
        if side == door_side:
            continue
        wx, wz = {"south": (cx, z2), "north": (cx, z1), "east": (x2, cz), "west": (x1, cz)}[side]
        conn = {"east": True, "west": True} if side in ("north", "south") else {"north": True, "south": True}
        for wyy in wy:
            out.append(f"block({wx}, {wyy}, {wz}, {_st('glass_pane', **conn)})")
    gconn = {"north": True, "south": True} if ridge == "x" else {"east": True, "west": True}
    wx, wz = (x1, cz) if ridge == "x" else (cx, z1)                 # a gable-end window, in the short wall
    for wyy in wy:
        out.append(f"block({wx}, {wyy}, {wz}, {_st('glass_pane', **gconn)})")
    out.append(f"block({cx}, {y + h - 1}, {cz}, {_st('lantern', hanging=True)})")
    out.append(f"gable_roof({x1}, {z1}, {x2}, {z2}, {y + h + 1}, {roof!r}, fill_block={walls!r}, ridge={ridge!r}, overhang=1, "
               f"slab={_st(roof[:-7] + '_slab', type='bottom')})")
    return _code(out)


def stone_arch_bridge(x, y, z, length=9, width=3, deck="stone_bricks", stone="cracked_stone_bricks", stair="stone_brick_stairs"):
    """A humped-free arched bridge along +x. The deck is at y, `length` cells from x, `width` cells along +z (width >= 3),
    with parapet walls on both edges and a stair ramp at each end. The arch stands on abutments at y-depth."""
    length, width = max(5, length), max(3, width)
    depth = max(3, length // 3)
    yb = y - depth
    stair = _stairs(stair)
    out = [f"# stone arch bridge, {length} long, deck at y={y}"]
    mid = (length - 1) / 2
    for i in range(length):
        t = (i - mid) / (length / 2)
        opening = int(round((depth - 1) * max(0.0, 1 - t * t)))
        for w in range(width):
            cx, cz = x + i, z + w
            if opening:
                out.append(f"fill({cx}, {yb + opening}, {cz}, {cx}, {y - 1}, {cz}, {stone!r})")
            else:
                out.append(f"fill({cx}, {yb}, {cz}, {cx}, {y - 1}, {cz}, {stone!r})")
            out.append(f"block({cx}, {y}, {cz}, {deck!r})")
    for i in range(length):                                          # parapets on both edges
        for w in (0, width - 1):
            out.append(f"block({x + i}, {y + 1}, {z + w}, 'stone_brick_wall')")
    for w in range(1, width - 1):                                    # ramps (centre lanes only)
        out.append(f"fill({x - 1}, {yb}, {z + w}, {x - 1}, {y - 1}, {z + w}, 'stone')")
        out.append(f"block({x - 1}, {y}, {z + w}, {_st(stair, facing='east', half='bottom', shape='straight')})")
        out.append(f"fill({x + length}, {yb}, {z + w}, {x + length}, {y - 1}, {z + w}, 'stone')")
        out.append(f"block({x + length}, {y}, {z + w}, {_st(stair, facing='west', half='bottom', shape='straight')})")
    return _code(out)


TREES = ("oak", "birch", "spruce", "dark_oak", "maple")


def tree(species, x, y, z, height=6):
    """A tree on a grass block at y-1. species: oak, birch, spruce, dark_oak or maple (autumn red-orange crown on a
    dark oak trunk)."""
    sp = str(species).lower()
    out = [f"# {sp} tree", f"block({x}, {y - 1}, {z}, 'grass_block')"]
    if sp == "maple":
        h = max(4, height)
        leaves = "B('azalea_leaves', persistent=True)"
        out += [f"ellipsoid({x}, {y + h - 1}, {z}, 3, 2.5, 3, {leaves})",
                f"line({x}, {y}, {z}, {x}, {y + h - 1}, {z}, B('dark_oak_log', axis='y'))"]
    elif sp in TREES:
        out.append(f"tree({x}, {y}, {z}, {sp!r}, {max(4, int(height))})")
    else:
        raise ValueError(f"species must be one of {', '.join(TREES)} (got {species!r})")
    return _code(out)


# ------------------------------------------------------------------ spiral stairs
def _ring_cw(xa, za, xb, zb):
    """Cells of the rectangle outline, clockwise seen from above (north up), starting at the north-west corner."""
    out = [(x, za) for x in range(xa, xb)]
    out += [(xb, z) for z in range(za, zb)]
    out += [(x, zb) for x in range(xb, xa, -1)]
    out += [(xa, z) for z in range(zb, za, -1)]
    return out


def _name_of(a, b):
    return {(1, 0): "east", (-1, 0): "west", (0, 1): "south", (0, -1): "north"}[(b[0] - a[0], b[1] - a[1])]


def _rail_for(wall):
    w = str(wall)
    if w.endswith("_bricks"):
        return w[:-7] + "_brick_wall"
    if w.endswith("_planks"):
        return w[:-7] + "_fence"
    if w in ("cobblestone", "mossy_cobblestone", "andesite", "diorite", "granite", "sandstone", "red_sandstone",
             "blackstone"):
        return w + "_wall"
    return "cobblestone_wall"


def _spiral_path(ring, y, height):
    """Walk the ring up: a stair on every cell that is not a corner, a flat landing on every corner (same height as the
    stair before it). Returns [(x, z, y, kind, facing)] with exactly `height` stairs, the first at y, the last at
    y + height - 1. One full turn climbs 4 * (side - 1) blocks, at least 4."""
    xs = [c[0] for c in ring]
    zs = [c[1] for c in ring]
    corners = {(a, b) for a in (min(xs), max(xs)) for b in (min(zs), max(zs))}
    items, cur, i, n = [], y - 1, 0, len(ring)
    while cur < y + height - 1:
        c = ring[i % n]
        if c in corners:
            items.append((c[0], c[1], cur, "landing", None))
        else:
            cur += 1
            items.append((c[0], c[1], cur, "stair", _name_of(c, ring[(i + 1) % n])))
        i += 1
    return items


def _spiral_tower(interior, wall_cells, ring, y, height, wall, stair, door, windows, core=()):
    """Shared by the round and the square tower. interior: floor cells inside the shell, wall_cells: the shell columns,
    door: (x, z, facing) in the shell, windows: shell cells that get panes every 7 blocks, core: pillar cells."""
    if height < 6:
        raise ValueError("height must be at least 6")
    stairs = _stairs(stair)
    ytop = y + height - 1                                           # top floor blocks; the feet stand at ytop + 1
    items = _spiral_path(ring, y, height)
    final = (items[-1][0], items[-1][1])
    nxt = ring[(ring.index(final) + 1) % len(ring)]
    # stairwell: the last turn's cells have no floor over them (3 free blocks over every step)
    hole = {(it[0], it[1]) for it in items if ytop - 3 <= it[2] <= ytop - 1}
    interior = set(interior)
    rails = set()
    for (hx, hz) in hole:
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (hx + a, hz + b)
            if q in interior and q not in hole and q not in (final, nxt):
                rails.add(q)
    rail = _rail_for(wall)
    out = [f"# spiral tower: {height} steps, ring of {len(ring)} cells, top floor at y={ytop}"]
    for (x, z) in sorted(interior | set(wall_cells)):               # ground floor
        out.append(f"block({x}, {y - 1}, {z}, {wall!r})")
    dx_, dz_, dfacing = door
    glass = set()
    for (wx, wz) in windows:
        for wy in range(y + 3, ytop - 1, 7):
            glass.add((wx, wy, wz))
            glass.add((wx, wy + 1, wz))
    top = ytop + 2                                                  # parapet: two blocks over the top floor
    for (x, z) in sorted(wall_cells):
        ys = [yy for yy in range(y + 2 if (x, z) == (dx_, dz_) else y, top + 1) if (x, yy, z) not in glass]
        start = prev = None
        for yy in ys + [None]:
            if start is not None and (yy is None or yy != prev + 1):
                out.append(f"fill({x}, {start}, {z}, {x}, {prev}, {z}, {wall!r})")
                start = None
            if yy is not None:
                if start is None:
                    start = yy
                prev = yy
    for (wx, wy, wz) in sorted(glass):
        out.append(f"block({wx}, {wy}, {wz}, 'glass_pane')")
    out.append(f"block({dx_}, {y}, {dz_}, {_st('oak_door', facing=dfacing, half='lower', hinge='left', open=False)})")
    out.append(f"block({dx_}, {y + 1}, {dz_}, {_st('oak_door', facing=dfacing, half='upper', hinge='left', open=False)})")
    for (x, z) in sorted(core):                                     # central pillar the stairs lean on
        out.append(f"fill({x}, {y}, {z}, {x}, {ytop - 1}, {z}, {wall!r})")
    for (x, z, yy, kind, facing) in items:
        if yy - y >= 1 and yy <= y + 2:                             # low steps sit on solid blocks (no cramped space under them)
            out.append(f"fill({x}, {y}, {z}, {x}, {yy - 1}, {z}, {wall!r})")
        if kind == "landing":
            out.append(f"block({x}, {yy}, {z}, {wall!r})")
        else:
            out.append(f"block({x}, {yy}, {z}, {_st(stairs, facing=facing, half='bottom', shape='straight')})")
    for (x, z) in sorted(interior):                                 # top floor with the stairwell hole
        if (x, z) in hole or (x, z) == final:
            continue
        out.append(f"block({x}, {ytop}, {z}, {(rail if (x, z) in rails else wall)!r})")
    return _code(out)


def round_tower_with_stair(cx, y, cz, radius, height, wall="stone_bricks", stair="stone_brick_stairs", direction="cw"):
    """A hollow round tower (shell of `wall`, outer radius `radius` >= 3 around cx, cz) with a spiral stair inside: floor
    at y-1, a door on the north side at y, windows every 7 blocks, a parapet two blocks over the top floor, which sits at
    y + height - 1 and is reached by the stair (stairwell hole in the floor with a railing). The stair climbs round a
    central pillar, a flat landing on every corner so turns happen on landings, 3 free blocks over every step."""
    import math
    if radius < 3:
        raise ValueError("radius must be at least 3")
    if direction not in ("cw", "ccw"):
        raise ValueError("direction must be cw or ccw")
    k = max(1, min(int((radius - 1.5) / 1.42), radius - 2))
    ring = _ring_cw(cx - k, cz - k, cx + k, cz + k)
    i0 = ring.index((cx, cz - k))
    ring = ring[i0:] + ring[:i0]                                    # start on the north side, in front of the door
    if direction == "ccw":
        ring = [ring[0]] + ring[1:][::-1]
    interior, wall_cells = [], []
    for x in range(cx - radius - 1, cx + radius + 2):
        for z in range(cz - radius - 1, cz + radius + 2):
            d = math.hypot(x - cx, z - cz)
            if d < radius - 0.5:
                interior.append((x, z))
            elif d < radius + 0.5:
                wall_cells.append((x, z))
    core = _ring_cw(cx - k + 1, cz - k + 1, cx + k - 1, cz + k - 1) if k >= 2 else [(cx, cz)]
    wset = set(wall_cells)
    if (cx, cz - radius) not in wset:
        raise ValueError("no wall cell for the door at this radius")
    off = round(radius * 0.7)
    wins = [c for c in ((cx + radius, cz), (cx - radius, cz), (cx, cz + radius),
                        (cx + off, cz + off), (cx - off, cz + off)) if c in wset]
    return _spiral_tower(interior, wall_cells, ring, y, height, wall, stair, (cx, cz - radius, "north"), wins, core)


def spiral_stair(cx, y, cz, radius, height, block="stone_brick_stairs", direction="cw"):
    """Spiral staircase for a round tower of outer radius `radius` (3 or more) around cx, cz, climbing `height` blocks from
    y: stairs round a pillar, a flat landing on every corner (turns happen on landings), one full turn climbs 4 or more
    so every step has 3 free blocks over it. Comes with its round shell, door, windows and top floor so it stands on its
    own; same as round_tower_with_stair."""
    return round_tower_with_stair(cx, y, cz, radius, height, "stone_bricks", block, direction)


def square_spiral_stair(x1, z1, size, y, height, block="stone_brick_stairs", wall="stone_bricks"):
    """A square tower (outer `size` x `size`, size 5 or more, north-west corner x1, z1) with a spiral stair along the
    inside of its walls: a stair on every wall cell, a flat landing in each of the four corners (turns happen on
    landings), 3 free blocks over every step. Door on the north side at y, windows, top floor at y + height - 1 with a
    stairwell hole and railing. The first stair is at y."""
    if size < 5:
        raise ValueError("size must be at least 5")
    xa, za, xb, zb = x1 + 1, z1 + 1, x1 + size - 2, z1 + size - 2
    ring = _ring_cw(xa, za, xb, zb)
    ring = ring[1:] + ring[:1]                                      # start one cell after the north-west corner
    interior = [(x, z) for x in range(xa, xb + 1) for z in range(za, zb + 1)]
    inner = set(interior)
    wall_cells = [(x, z) for x in range(x1, x1 + size) for z in range(z1, z1 + size) if (x, z) not in inner]
    wins = [(x1 + size - 1, z1 + size // 2), (x1, z1 + size // 2), (x1 + size // 2, z1 + size - 1)]
    return _spiral_tower(interior, wall_cells, ring, y, height, wall, block, (xa + 1, z1, "north"), wins)


# ------------------------------------------------------------------ house parts (quality: docs/QUALITY.md)
# Rules taken from good survival houses: log frames that stick out of the wall, roofs that overhang 1-2 blocks with a trim,
# framed windows with shutters and flower boxes, porches and balconies on posts, a chimney, a garden and a path.
WOOD_NAMES = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry", "bamboo", "crimson",
              "warped", "pale_oak")
_AXIS = {"north": "x", "south": "x", "east": "z", "west": "z"}


def _wall_cells(x1, z1, x2, z2, facing):
    """The cells of a straight wall from (x1, z1) to (x2, z2) and its outward step."""
    dx, dz = _dir(facing)
    if x1 != x2 and z1 != z2:
        raise ValueError("a wall must be straight: x1 == x2 or z1 == z2")
    if (x1 != x2 and dz == 0) or (z1 != z2 and dx == 0):
        raise ValueError(f"a wall along x faces north or south, a wall along z faces east or west (got {facing!r})")
    cells = [(x, z) for x in range(min(x1, x2), max(x1, x2) + 1) for z in range(min(z1, z2), max(z1, z2) + 1)]
    return cells, (dx, dz)


def _posts(cells, spacing):
    return [c for i, c in enumerate(cells) if i % max(2, int(spacing)) == 0 or i == len(cells) - 1]


def framed_wall(x1, z1, x2, z2, y, h, facing, fill=None, frame=None, spacing=4, style=None):
    """A timber-framed wall: `fill` infill from y to y+h-1 on the straight line (x1, z1)-(x2, z2), log posts in the wall
    at both ends and every `spacing` blocks, and a frame that sticks out 1 block on the `facing` side: posts from y-1 to
    the top and log beams along the bottom (y-1) and top (y+h-1) rows. Leave the cells between posts for windows/doors.
    style = a WALL_STYLES name for fill and frame not given (default 'light': birch planks in an oak log frame)."""
    fill, frame = _style(style, fill, frame)
    cells, (dx, dz) = _wall_cells(x1, z1, x2, z2, facing)
    along = _AXIS[facing]
    top = y + max(2, int(h)) - 1
    a, b = cells[0], cells[-1]
    out = [f"# framed wall facing {facing}, {len(cells)} long, rows {y}..{top}",
           f"fill({a[0]}, {y}, {a[1]}, {b[0]}, {top}, {b[1]}, {fill!r})"]
    for (cx, cz) in _posts(cells, spacing):
        out.append(f"fill({cx}, {y}, {cz}, {cx}, {top}, {cz}, {_st(frame, axis='y')})")
        out.append(f"fill({cx + dx}, {y - 1}, {cz + dz}, {cx + dx}, {top}, {cz + dz}, {_st(frame, axis='y')})")
    for row in (y - 1, top):
        out.append(f"fill({a[0] + dx}, {row}, {a[1] + dz}, {b[0] + dx}, {row}, {b[1] + dz}, {_st(frame, axis=along)})")
    return _code(out)


def framed_house(x1, z1, x2, z2, y, floors=1, storey=4, fill=None, frame=None, floor="spruce_planks",
                 foundation="cobblestone", spacing=4, skip=(), clear=False, flat=(), style=None):
    """The body of a timber-framed house: foundation at y-1, `floors` storeys of `storey` free blocks (walls on the
    outline x1..x2, z1..z2), plank floors between storeys and a ceiling on top, log posts in the walls every `spacing`
    blocks and a frame sticking out 1 block (posts, a beam on every floor line, thick corners). The ceiling is at
    y + floors * (storey + 1) - 1: the roof's eaves go one higher. skip = sides without a wall (a wing joined to another
    building, e.g. ['east']); flat = sides whose frame stays in the wall (where a lower wing and its roof join);
    clear=True empties the rooms first. Then add windows (window_with_box with box=trapdoor_of(frame): a planter of
    soft mixed plants under every second window of the lower floors, planter=False - a sill - under the rest), a porch
    or door, and the roof.
    style = a WALL_STYLES name for fill and frame not given: 'light' (birch planks in oak logs, the reference look and
    the default), 'oak' (oak planks in spruce logs), 'stripped', 'plaster', 'classic'; 'dark' (spruce planks in dark
    oak logs) only when the user asks for a dark build.
    Tip: a side of 4k+1 blocks with spacing 4 leaves 3-block bays, a window or door in the middle of each; 5k+1 blocks
    with spacing 5 leaves 4-block bays for 2-wide windows."""
    fill, frame = _style(style, fill, frame)
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    if x2 - x1 < 3 or z2 - z1 < 3:
        raise ValueError("a house needs at least 4 x 4 blocks")
    floors, storey = max(1, int(floors)), max(3, int(storey))
    skip = {str(s).lower() for s in (skip or ())}
    flat = {str(s).lower() for s in (flat or ())}
    bad = (skip | flat) - set(DIRS)
    if bad:
        raise ValueError(f"skip and flat take north, south, east, west (got {sorted(bad)})")
    top = y + floors * (storey + 1) - 1
    lines = [y + k * (storey + 1) + storey for k in range(floors)]
    sides = {"north": (x1, z1, x2, z1), "south": (x1, z2, x2, z2), "west": (x1, z1, x1, z2), "east": (x2, z1, x2, z2)}
    out = [f"# framed house x {x1}..{x2}, z {z1}..{z2}, {floors} floor(s), ceiling at y={top}",
           f"fill({x1}, {y - 1}, {z1}, {x2}, {y - 1}, {z2}, {foundation!r})",
           f"fill({x1 + 1}, {y - 1}, {z1 + 1}, {x2 - 1}, {y - 1}, {z2 - 1}, {floor!r})"]
    if clear:
        out.append(f"fill({x1 + 1}, {y}, {z1 + 1}, {x2 - 1}, {top - 1}, {z2 - 1}, 'air')")
    for yk in lines:
        out.append(f"fill({x1 + 1}, {yk}, {z1 + 1}, {x2 - 1}, {yk}, {z2 - 1}, {floor!r})")
    for side, (a, b, c, d) in sides.items():
        if side in skip:
            continue
        dx, dz = DIRS[side]
        along = _AXIS[side]
        out.append(f"fill({a}, {y}, {b}, {c}, {top}, {d}, {fill!r})")
        for yk in lines:
            out.append(f"fill({a}, {yk}, {b}, {c}, {yk}, {d}, {_st(frame, axis=along)})")
        cells = [(x, z) for x in range(a, c + 1) for z in range(b, d + 1)]
        for (cx, cz) in _posts(cells, spacing):
            out.append(f"fill({cx}, {y}, {cz}, {cx}, {top}, {cz}, {_st(frame, axis='y')})")
            if side not in flat:
                out.append(f"fill({cx + dx}, {y - 1}, {cz + dz}, {cx + dx}, {top}, {cz + dz}, {_st(frame, axis='y')})")
        for row in ([y - 1] + lines) if side not in flat else ():
            out.append(f"fill({a + dx}, {row}, {b + dz}, {c + dx}, {row}, {d + dz}, {_st(frame, axis=along)})")
    for (cx, cz, s1, s2) in ((x1 - 1, z1 - 1, "west", "north"), (x2 + 1, z1 - 1, "east", "north"),
                             (x1 - 1, z2 + 1, "west", "south"), (x2 + 1, z2 + 1, "east", "south")):
        if not ({s1, s2} & (skip | flat)):
            out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {top}, {cz}, {_st(frame, axis='y')})")
    return _code(out)


# Window box planting: soft, pale and green plants mixed in each box. One strong colour (poppies) under every window
# reads as a row of red squares from afar (reviewer, 1.15.0 manor), so it is never the default.
BOX_PLANTS = ("azure_bluet", "fern", "oxeye_daisy", "lily_of_the_valley", "azalea")


def _box_plants(flower):
    if flower is None:
        return BOX_PLANTS
    if isinstance(flower, (list, tuple)):
        return tuple(str(f) for f in flower) or BOX_PLANTS
    return (str(flower),)


def trapdoor_of(frame):
    """The trapdoor in a frame's wood: oak_log -> oak_trapdoor, stripped_spruce_log -> spruce_trapdoor (oak for stone)."""
    n = str(frame or "oak_log").replace("minecraft:", "").split("[")[0].replace("stripped_", "")
    for suf in ("_log", "_wood", "_planks", "_stem", "_hyphae"):
        if n.endswith(suf):
            n = n[: -len(suf)]
            break
    return n + "_trapdoor" if n in WOOD_NAMES else "oak_trapdoor"


def window_with_box(x, y, z, facing, width=1, height=2, glass="glass_pane", shutter="birch_trapdoor",
                    box="oak_trapdoor", flower=None, lintel="stripped_birch_log", wall=None, planter=True):
    """A white-framed window in a wall: `width` x `height` panes, the lowest-left pane at (x, y, z) (width runs east or
    south along the wall), a light (stripped birch) lintel over it, open birch trapdoor shutters on both sides and,
    with planter=True, a planter directly under the panes (a grass block in front of the wall row under each bottom
    pane with a plant on it, never in front of a pane, `box` trapdoors round its front, sides and bottom - give it the
    frame's wood, trapdoor_of(frame)). The plants default to a soft mix (BOX_PLANTS: azure bluet, fern, oxeye daisy,
    lily of the valley, azalea); `flower` = one kind or a list to mix. planter=False puts a plain `box` trapdoor sill
    under the panes instead. Put planters only under SOME windows (every second one, ground and first floor): a strong
    flower colour under every window reads as a row of red squares from afar. All on the `facing` (outside) side.
    wall = a block for a small wall piece round it (a window on its own); None keeps the wall already built."""
    dx, dz = _dir(facing)
    ax, az = (1, 0) if _AXIS[facing] == "x" else (0, 1)
    width, height = max(1, int(width)), max(1, int(height))
    conn = {"east": True, "west": True} if ax else {"north": True, "south": True}
    neg, pos = ("west", "east") if ax else ("north", "south")
    plants = _box_plants(flower)
    out = [f"# window {width} x {height} facing {facing} with shutters and " + ("a planter" if planter else "a sill")]
    if wall:
        out.append(f"fill({x - 2 * ax}, {y - 2}, {z - 2 * az}, {x + (width + 1) * ax}, {y + height + 1}, "
                   f"{z + (width + 1) * az}, {wall!r})")
    for i in range(width):
        cx, cz = x + ax * i, z + az * i
        for k in range(height):
            out.append(f"block({cx}, {y + k}, {cz}, {_st(glass, **conn) if glass.endswith('_pane') else repr(glass)})")
        if not planter:
            out.append(f"block({cx + dx}, {y - 1}, {cz + dz}, {_st(box, facing=facing, half='top', open=False)})")
            continue
        plant = plants[(i + abs(x) + abs(z) + abs(y)) % len(plants)]            # mixed along the box, not one colour
        out.append(f"block({cx + dx}, {y - 2}, {cz + dz}, 'grass_block')")      # the box sits under the sill row,
        out.append(f"block({cx + dx}, {y - 1}, {cz + dz}, {plant!r})")          # so no plant hides a pane
        out.append(f"block({cx + 2 * dx}, {y - 2}, {cz + 2 * dz}, {_st(box, facing=facing, half='bottom', open=True)})")
        out.append(f"block({cx + dx}, {y - 3}, {cz + dz}, {_st(box, facing=facing, half='top', open=False)})")
    out.append(f"fill({x - ax}, {y + height}, {z - az}, {x + width * ax}, {y + height}, {z + width * az}, "
               f"{_st(lintel, axis=_AXIS[facing])})")
    for side, (sx, sz) in ((neg, (x - ax, z - az)), (pos, (x + width * ax, z + width * az))):
        for k in range(height):
            out.append(f"block({sx + dx}, {y + k}, {sz + dz}, {_st(shutter, facing=facing, half='bottom', open=True)})")
        if planter:
            out.append(f"block({sx + dx}, {y - 1}, {sz + dz}, {_st(box, facing=side, half='bottom', open=True)})")
    return _code(out)


def porch(x, y, z, facing, width=5, depth=3, wood="oak", post="oak_log", roof="oak_stairs", steps=0, path=2,
          path_block="dirt_path", door=True):
    """A covered porch at a door: the door at (x, y, z) in the wall (facing out), a plank deck at y-1 in front of it
    (`width` wide, `depth` deep), log posts on the front corners, beams at y+3, a low roof at y+4 with stair edges, a
    lantern under the front beam, `steps` stairs down from the deck (the ground is then `steps` lower than the deck)
    and a `path` of path blocks leading away. Keeps 3 free blocks over the deck."""
    dx, dz = _dir(facing)
    px, pz = (1, 0) if _AXIS[facing] == "x" else (0, 1)
    back = OPP[facing]
    half = max(1, int(width) // 2)
    depth = max(2, int(depth))
    steps, path = max(0, int(steps)), max(0, int(path))
    planks = wood + "_planks"
    rst = _stairs(roof)
    slab = rst[:-7] + "_slab"
    left, right = ("west", "east") if px else ("north", "south")

    def at(k, w):
        return x + dx * k + px * w, z + dz * k + pz * w
    out = [f"# porch facing {facing}, {2 * half + 1} wide, {depth} deep"]
    base = y - 1 - steps
    for k in range(1, depth + 1):
        for w in range(-half, half + 1):
            cx, cz = at(k, w)
            if steps:
                out.append(f"fill({cx}, {base}, {cz}, {cx}, {y - 2}, {cz}, 'cobblestone')")
            out.append(f"block({cx}, {y - 1}, {cz}, {planks!r})")
            out.append(f"fill({cx}, {y}, {cz}, {cx}, {y + 2}, {cz}, 'air')")
    for w in (-half, half):
        cx, cz = at(depth, w)
        out.append(f"fill({cx}, {y}, {cz}, {cx}, {y + 2}, {cz}, {_st(post, axis='y')})")
    for w in range(-half, half + 1):
        cx, cz = at(depth, w)
        out.append(f"block({cx}, {y + 3}, {cz}, {_st(post, axis=_AXIS[facing])})")
    for k in range(1, depth):
        for w in (-half, half):
            cx, cz = at(k, w)
            out.append(f"block({cx}, {y + 3}, {cz}, {_st(post, axis=_AXIS[left])})")
    for k in range(1, depth + 2):
        for w in range(-half - 1, half + 2):
            cx, cz = at(k, w)
            if k == depth + 1 and abs(w) == half + 1:
                st = _st(slab, type="top")                           # corner: no stair turns on one block
            elif k == depth + 1:
                st = _st(rst, facing=back, half="bottom")
            elif w == -half - 1:
                st = _st(rst, facing=right, half="top")              # top halves: the porch roof can sit under eaves
            elif w == half + 1:
                st = _st(rst, facing=left, half="top")
            else:
                st = _st(slab, type="top")
            out.append(f"block({cx}, {y + 4}, {cz}, {st})")
    cx, cz = at(depth, 0)
    out.append(f"block({cx}, {y + 2}, {cz}, {_st('lantern', hanging=True)})")
    for i in range(steps):
        for w in (-1, 0, 1):
            cx, cz = at(depth + 1 + i, w)
            if y - 2 - i >= base:
                out.append(f"fill({cx}, {base}, {cz}, {cx}, {y - 2 - i}, {cz}, 'cobblestone')")
            out.append(f"block({cx}, {y - 1 - i}, {cz}, "
                       f"{_st(_stairs(wood), facing=back, half='bottom', shape='straight')})")
    for i in range(path):
        for w in (-1, 0, 1):
            cx, cz = at(depth + 1 + steps + i, w)
            out.append(f"block({cx}, {base - 1}, {cz}, 'dirt')")
            out.append(f"block({cx}, {base}, {cz}, {path_block!r})")
    if door:
        out.append(f"block({x}, {y - 1}, {z}, {planks!r})")
        out.append(f"block({x}, {y}, {z}, {_st(wood + '_door', facing=facing, half='lower', hinge='left', open=False)})")
        out.append(f"block({x}, {y + 1}, {z}, {_st(wood + '_door', facing=facing, half='upper', hinge='left', open=False)})")
    return _code(out)


def balcony(x, y, z, facing, length=5, depth=2, wood="oak", post="oak_log", ground_y=None, door=False, gap=None):
    """A balcony: a plank floor at height y sticking out `depth` blocks on the `facing` side of a wall, `length` blocks
    along it from (x, z) (the floor cell next to the wall; length runs east or south). A fence railing round the open
    edges, log posts with lanterns on the outer corners, upside-down stair brackets under the floor at both ends, and
    posts down to ground_y (the top block of the ground) when given. door=True puts a door in the wall behind the middle.
    gap = 'start' or 'end' leaves the railing open at that end (w = 0 or the last cell) for an external_stair whose top
    landing (at height y) ends next to it: the balcony access."""
    if gap not in (None, "start", "end"):
        raise ValueError("gap must be None, 'start' or 'end'")
    dx, dz = _dir(facing)
    px, pz = (1, 0) if _AXIS[facing] == "x" else (0, 1)
    length, depth = max(3, int(length)), max(1, int(depth))
    fence = wood + "_fence"

    def at(k, w):
        return x + dx * k + px * w, z + dz * k + pz * w
    out = [f"# balcony facing {facing}, {length} x {depth}, floor at y={y}"]
    for k in range(depth):
        for w in range(length):
            cx, cz = at(k, w)
            out.append(f"block({cx}, {y}, {cz}, {wood + '_planks'!r})")
            if k == depth - 1 and w in (0, length - 1):
                out.append(f"block({cx}, {y + 1}, {cz}, {_st(post, axis='y')})")
                out.append(f"block({cx}, {y + 2}, {cz}, {_st('lantern', hanging=False)})")
            elif k == depth - 1 or w in (0, length - 1):
                if k < depth - 1 and ((gap == "start" and w == 0) or (gap == "end" and w == length - 1)):
                    continue                                         # the opening for the stair
                out.append(f"block({cx}, {y + 1}, {cz}, {fence!r})")
    for w in (0, length - 1):
        for k in range(depth):
            cx, cz = at(k, w)
            out.append(f"block({cx}, {y - 1}, {cz}, {_st(_stairs(wood), facing=OPP[facing], half='top')})")
        cx, cz = at(depth - 1, w)
        if ground_y is not None and int(ground_y) < y - 1:
            out.append(f"fill({cx}, {int(ground_y) + 1}, {cz}, {cx}, {y - 1}, {cz}, {_st(post, axis='y')})")
    if door:
        cx, cz = at(-1, length // 2)
        out.append(f"block({cx}, {y + 1}, {cz}, {_st(wood + '_door', facing=facing, half='lower', hinge='left', open=False)})")
        out.append(f"block({cx}, {y + 2}, {cz}, {_st(wood + '_door', facing=facing, half='upper', hinge='left', open=False)})")
    return _code(out)


def external_stair(x, y, z, dir, height, width=2, flight=4, landing=2, block="oak_stairs", support="oak_planks",
                   rail="oak_fence", rails="both"):
    """An outside stair up to a terrace, balcony or upper door: straight flights of `flight` bottom stairs facing uphill
    (1 up per cell), a flat landing of `landing` cells after every flight, climbing `height` steps in all. The first step
    is at (x, y, z) on ground at y-1; `width` cells wide to the right-hand side of `dir`. The top landing's blocks are at
    y + height - 1, so a terrace or balcony floor at that height continues it (balcony(..., gap=...) leaves the railing
    open). Solid `support` under every step and landing down to y-1; a stringer wall with a `rail` fence on top along
    the sides in `rails` ('both', 'left', 'right' or 'none'; left = the side opposite the width; use one side when the
    stair runs along a wall). Never turns on a stair, so no jump steps and no corner turns."""
    dx, dz = _dir(dir)
    px, pz = -dz, dx
    height, width = max(1, int(height)), max(1, int(width))
    flight, landing = max(1, int(flight)), max(1, int(landing))
    if rails not in ("both", "left", "right", "none"):
        raise ValueError("rails must be 'both', 'left', 'right' or 'none'")
    stairs = _stairs(block)
    sides = {"both": (-1, width), "left": (-1,), "right": (width,), "none": ()}[rails]
    out = [f"# external stair {dir}, {height} steps in flights of {flight} with landings of {landing}"]
    off, top, done = 0, y - 1, 0
    while done < height:
        n = min(flight, height - done)
        for i in range(n):
            top += 1
            for w in range(width):
                cx, cz = x + dx * off + px * w, z + dz * off + pz * w
                if top > y:
                    out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {top - 1}, {cz}, {support!r})")
                else:
                    out.append(f"block({cx}, {y - 1}, {cz}, {support!r})")
                out.append(f"block({cx}, {top}, {cz}, {_st(stairs, facing=dir, half='bottom', shape='straight')})")
            for w in sides:
                sx, sz = x + dx * off + px * w, z + dz * off + pz * w
                out.append(f"fill({sx}, {y - 1}, {sz}, {sx}, {top}, {sz}, {support!r})")
                out.append(f"block({sx}, {top + 1}, {sz}, {rail!r})")
            off += 1
        done += n
        for j in range(landing):                                     # flat landing, the same height as the last step
            for w in range(width):
                cx, cz = x + dx * off + px * w, z + dz * off + pz * w
                out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {top}, {cz}, {support!r})")
            last = done >= height and j == landing - 1
            for w in sides:
                sx, sz = x + dx * off + px * w, z + dz * off + pz * w
                out.append(f"fill({sx}, {y - 1}, {sz}, {sx}, {top}, {sz}, {support!r})")
                if not last:
                    out.append(f"block({sx}, {top + 1}, {sz}, {rail!r})")
            off += 1
    return _code(out)


def storey_band(x1, z1, x2, z2, y, stairs="spruce_stairs", out=2, skip=(), gaps=()):
    """A storey band (pent roof, jetty skirt) round the walls x1..x2, z1..z2: a row of stairs at height y, `out` blocks
    outside the walls (2 for a framed_house, whose frame sticks out 1), the high side against the wall, slabs on the
    corners. Put it at or 1 below a floor line between two storeys: it splits a tall facade into layers like the reference
    manors and gives the roof a second height. skip = sides without a band (where a wing joins); gaps = [[x1, z1, x2,
    z2], ...] columns to leave open (a porch roof or a balcony over it, a wing roof)."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    o = max(1, int(out))
    skip = {str(s).lower() for s in (skip or ())}
    if skip - set(DIRS):
        raise ValueError("skip takes north, south, east, west")
    st = _stairs(stairs)
    slab = _st(st[:-7] + "_slab", type="bottom")
    lo_x, hi_x, lo_z, hi_z = x1 - o, x2 + o, z1 - o, z2 + o
    cells = {}
    for side, facing in (("north", "south"), ("south", "north"), ("west", "east"), ("east", "west")):
        if side in skip:
            continue
        if side in ("north", "south"):
            zz = lo_z if side == "north" else hi_z
            for xx in range(lo_x, hi_x + 1):
                cells[(xx, y, zz)] = _st(st, facing=facing, half="bottom")
        else:
            xx = lo_x if side == "west" else hi_x
            for zz in range(lo_z, hi_z + 1):
                cells[(xx, y, zz)] = _st(st, facing=facing, half="bottom")
    for (cx, cz) in ((lo_x, lo_z), (hi_x, lo_z), (lo_x, hi_z), (hi_x, hi_z)):
        if (cx, y, cz) in cells:
            cells[(cx, y, cz)] = slab                                # no stair turns on one block
    for g in gaps or ():
        gx1, gz1, gx2, gz2 = (int(v) for v in g)
        for key in [k for k in cells if min(gx1, gx2) <= k[0] <= max(gx1, gx2) and min(gz1, gz2) <= k[2] <= max(gz1, gz2)]:
            del cells[key]
    return _code([f"# storey band round x {x1}..{x2}, z {z1}..{z2} at y={y}, {o} out"] + _emit(cells))


def _emit(cells):
    """Script lines for {(x, y, z): state text}: runs of the same state along x or z become one fill()."""
    out, done = [], set()
    for (x, y, z) in sorted(cells, key=lambda p: (p[1], p[2], p[0])):
        if (x, y, z) in done:
            continue
        st = cells[(x, y, z)]
        x2 = x
        while (x2 + 1, y, z) in cells and cells[(x2 + 1, y, z)] == st and (x2 + 1, y, z) not in done:
            x2 += 1
        z2 = z
        if x2 == x:
            while (x, y, z2 + 1) in cells and cells[(x, y, z2 + 1)] == st and (x, y, z2 + 1) not in done:
                z2 += 1
        for xx in range(x, x2 + 1):
            for zz in range(z, z2 + 1):
                done.add((xx, y, zz))
        if (x2, z2) == (x, z):
            out.append(f"block({x}, {y}, {z}, {st})")
        else:
            out.append(f"fill({x}, {y}, {z}, {x2}, {y}, {z2}, {st})")
    return out


def _is_roof_piece(st):
    """A bottom stair or bottom slab: the roof pieces the path checks would read as steps."""
    return ("_stairs'" in st and "half='bottom'" in st) or ("_slab'" in st and "type='bottom'" in st)


def _settle(cells, trim_block=None):
    """Clean up where roofs overlap. A stair or slab with any block 1-2 above it is hidden under another roof (it would
    read as a step with no head room): removed. Where two slopes meet in a valley (stairs facing across each other)
    the stair becomes a full `trim_block`, a valley rafter, so no stair turns or jumps on the roof."""
    for (x, y, z) in list(cells):
        st = cells.get((x, y, z))
        if st and _is_roof_piece(st) and ((x, y + 1, z) in cells or (x, y + 2, z) in cells):
            del cells[(x, y, z)]
    if trim_block:
        def facing(st):
            return st.split("facing=", 1)[1].split("'", 2)[1] if "_stairs'" in st and "facing=" in st else None
        for (x, y, z) in sorted(cells):
            st = cells[(x, y, z)]
            if not _is_roof_piece(st):
                continue
            f = facing(st)
            for name_, (a, c) in DIRS.items():
                bad = False
                for dy in (-1, 0, 1):
                    q = cells.get((x + a, y + dy, z + c))
                    if not q or not _is_roof_piece(q):
                        continue
                    g = facing(q)
                    if f and g and g != f and g != OPP[f]:
                        bad = True                                   # two slopes meet across each other
                    elif dy == 1 and f != name_:
                        bad = True                                   # a step up that is not this slope going on
                if bad:
                    cells[(x, y, z)] = repr(trim_block)
                    break
    return cells


def _gable_cells(x1, z1, x2, z2, y, stairs, trim, ridge, o, fill, ends, rafter=True):
    """{(x, y, z): state text} of a trimmed gable roof (see gable_roof_trim)."""
    tslab = _st(trim[:-7] + "_slab", type="bottom")
    lo_f, hi_f = ("south", "north") if ridge == "x" else ("east", "west")
    if ridge == "x":
        a, b = z1 - o, z2 + o
        run = list(range(x1 - (o if "lo" in ends else 0), x2 + (o if "hi" in ends else 0) + 1))
        gab, glo, ghi = (z1, z2), x1, x2
    else:
        a, b = x1 - o, x2 + o
        run = list(range(z1 - (o if "lo" in ends else 0), z2 + (o if "hi" in ends else 0) + 1))
        gab, glo, ghi = (x1, x2), z1, z2

    def put(v, c, yy, st):
        cells[(v, yy, c) if ridge == "x" else (c, yy, v)] = st
    cells = {}
    k = 0
    while a + k <= b - k:
        yy = y + k
        for v in run:
            edge = (v == run[0] and "lo" in ends) or (v == run[-1] and "hi" in ends)
            mat = trim if edge or k == 0 else stairs
            if a + k == b - k:
                put(v, a + k, yy, tslab)
            elif a + k + 1 == b - k:                                 # even span: the top pair is the trim ridge
                put(v, a + k, yy, _st(trim, facing=lo_f, half="bottom"))
                put(v, b - k, yy, _st(trim, facing=hi_f, half="bottom"))
            else:
                put(v, a + k, yy, _st(mat, facing=lo_f, half="bottom"))
                put(v, b - k, yy, _st(mat, facing=hi_f, half="bottom"))
                if k < o and a + k + 1 < b - k - 1:                  # soffit under the overhang: it holds the eave up
                    put(v, a + k + 1, yy, _st(trim, facing=hi_f, half="top"))
                    put(v, b - k - 1, yy, _st(trim, facing=lo_f, half="top"))
        if fill:
            for c in range(max(a + k + 1, gab[0]), min(b - k - 1, gab[1]) + 1):
                for g, e in ((glo, "lo"), (ghi, "hi")):
                    if e in ends:
                        put(g, c, yy, repr(fill))
        k += 1
    if rafter and len(ends) < 2:                                     # the joint with the taller building: a rafter
        v = run[0] if "lo" not in ends else run[-1]
        for key in [p for p in cells if (p[0] if ridge == "x" else p[2]) == v]:
            cells[key] = repr(_full(trim))
    return cells


def _gable_args(x1, z1, x2, z2, ridge, open_end):
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    ridge = ridge or ("x" if x2 - x1 >= z2 - z1 else "z")
    if ridge not in ("x", "z"):
        raise ValueError("ridge must be 'x' or 'z'")
    lo, hi = ("west", "east") if ridge == "x" else ("north", "south")
    if open_end not in (None, lo, hi):
        raise ValueError(f"open_end must be {lo!r} or {hi!r} for ridge {ridge!r}")
    ends = tuple(e for e, n in (("lo", lo), ("hi", hi)) if n != open_end)
    if open_end == hi:
        x2, z2 = (x2 - 1, z2) if ridge == "x" else (x2, z2 - 1)
    elif open_end == lo:
        x1, z1 = (x1 + 1, z1) if ridge == "x" else (x1, z1 + 1)
    return x1, z1, x2, z2, ridge, ends


def gable_roof_trim(x1, z1, x2, z2, y, stairs=ROOF_DEFAULT, trim=TRIM_DEFAULT, ridge=None, overhang=1, fill="oak_planks",
                    open_end=None):
    """A gable roof with a trim over the walls x1..x2, z1..z2 (eaves at y): `stairs` slopes (default teal, the reference
    look; a dark or grey roof only when the user asks); the eave row, the barge boards on the gable ends and the ridge
    in `trim` (default oak); eaves `overhang` blocks past the walls (2 when the walls have a
    frame sticking out); gable triangles filled with `fill`. ridge 'x' or 'z' (default: along the longer side).
    open_end = 'west'/'east' (ridge x) or 'north'/'south' (ridge z): that end joins a taller building, so no overhang,
    barge or gable there and the roof stops 1 block short of that wall."""
    x1, z1, x2, z2, ridge, ends = _gable_args(x1, z1, x2, z2, ridge, open_end)
    o = max(0, int(overhang))
    cells = _gable_cells(x1, z1, x2, z2, y, _stairs(stairs), _stairs(trim), ridge, o, fill, ends)
    return _code([f"# gable roof, {_stairs(trim)[:-7]} trim, x {x1}..{x2}, z {z1}..{z2}, eaves at y={y}, overhang {o}"]
                 + _emit(_settle(cells)))


def hip_roof_trim(x1, z1, x2, z2, y, stairs=ROOF_DEFAULT, trim=TRIM_DEFAULT, overhang=1, fill="oak_planks"):
    """A four-sided (hip) roof over the walls x1..x2, z1..z2, eaves at y, `overhang` past the walls; the eave ring and the
    ridge cap in `trim`; each ring of stairs stands on a ring of `fill` so nothing floats."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    o = max(0, int(overhang))
    stairs, tst = _stairs(stairs), _stairs(trim)
    cells = {}
    ax, bx, az, bz = x1 - o, x2 + o, z1 - o, z2 + o
    k = 0
    while ax + k <= bx - k and az + k <= bz - k:
        yy = y + k
        lx, hx, lz, hz = ax + k, bx - k, az + k, bz - k
        if k:
            for xx in range(lx, hx + 1):
                for zz in range(lz, hz + 1):
                    if xx in (lx, hx) or zz in (lz, hz):
                        cells[(xx, yy - 1, zz)] = repr(fill)
        if hx - lx <= 1 or hz - lz <= 1:
            for xx in range(lx, hx + 1):
                for zz in range(lz, hz + 1):
                    cells[(xx, yy, zz)] = _st(tst[:-7] + "_slab", type="bottom")
            break
        mat = tst if k == 0 else stairs
        for xx in range(lx, hx + 1):
            for zz in range(lz, hz + 1):
                if zz == lz:
                    cells[(xx, yy, zz)] = _st(mat, facing="south", half="bottom")
                elif zz == hz:
                    cells[(xx, yy, zz)] = _st(mat, facing="north", half="bottom")
                elif xx == lx:
                    cells[(xx, yy, zz)] = _st(mat, facing="east", half="bottom")
                elif xx == hx:
                    cells[(xx, yy, zz)] = _st(mat, facing="west", half="bottom")
        k += 1
    for (xx, yy, zz) in list(cells):                                 # corners: a slab, so no stair turns on one block
        if (xx in (ax + yy - y, bx - yy + y)) and (zz in (az + yy - y, bz - yy + y)) and _is_roof_piece(cells[(xx, yy, zz)]):
            cells[(xx, yy, zz)] = _st(tst[:-7] + "_slab", type="bottom")
    return _code([f"# hip roof, {tst[:-7]} trim, x {x1}..{x2}, z {z1}..{z2}, eaves at y={y}"] + _emit(_settle(cells)))


def cross_gable_roof(x1, z1, x2, z2, y, stairs=ROOF_DEFAULT, trim=TRIM_DEFAULT, fill="oak_planks", front="south",
                     wing=None, overhang=1):
    """A layered roof: a trimmed gable roof along the long side of x1..x2, z1..z2 plus a lower cross gable over the
    middle of the `front` wall with its own gable end facing out, `wing` blocks wide (odd; default about a third of the
    front). It breaks a long plain roof plane like the big survival manors."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    front = str(front).lower()
    _dir(front)
    along_x = front in ("north", "south")
    span, depth = ((x2 - x1), (z2 - z1)) if along_x else ((z2 - z1), (x2 - x1))
    w = int(wing) if wing else max(3, (span + 1) // 3)
    w = max(3, min(w, depth - 2, span - 2))
    w -= 1 - w % 2
    o = max(0, int(overhang))
    st, tr = _stairs(stairs), _stairs(trim)
    cells = _gable_cells(*_gable_args(x1, z1, x2, z2, "x" if along_x else "z", None)[:4], y, st, tr,
                         "x" if along_x else "z", o, fill, ("lo", "hi"))
    c = ((x1 + x2) if along_x else (z1 + z2)) // 2
    a, b = c - w // 2, c + w // 2
    if along_x:
        mid = (z1 + z2) // 2
        box = (a, mid, b, z2) if front == "south" else (a, z1, b, mid)
        args = _gable_args(*box, "z", "north" if front == "south" else "south")
    else:
        mid = (x1 + x2) // 2
        box = (mid, a, x2, b) if front == "east" else (x1, a, mid, b)
        args = _gable_args(*box, "x", "west" if front == "east" else "east")
    cross = _gable_cells(*args[:4], y, st, tr, args[4], o, fill, args[5], rafter=False)
    for (cx, cy, cz), s in cross.items():                         # the cross gable wins where it is higher
        top = max((yy for (xx, yy, zz) in cells if (xx, zz) == (cx, cz)), default=None)
        if top is None or cy >= top or not _is_roof_piece(s):
            for yy in [yy for (xx, yy, zz) in cells if (xx, zz) == (cx, cz) and yy < cy and _is_roof_piece(cells[(xx, yy, zz)])]:
                del cells[(cx, yy, cz)]
            cells[(cx, cy, cz)] = s
    return _code([f"# layered roof: gable over x {x1}..{x2}, z {z1}..{z2} with a cross gable to the {front}, eaves at y={y}"]
                 + _emit(_settle(cells, _full(tr))))


def chimney(x, y, z, height=8, block="bricks", cap="campfire"):
    """A chimney column at (x, z) from y up `height` blocks of `block`, a lit campfire (smoke) or a `cap` block on top.
    Put it against a gable wall or through the roof; its top should stand 2+ blocks above the roof around it."""
    height = max(3, int(height))
    capst = _st("campfire", lit=True, signal_fire=False) if cap == "campfire" else repr(cap)
    return _code([f"# chimney at x {x}, z {z}, {height} high",
                  f"fill({x}, {y}, {z}, {x}, {y + height - 1}, {z}, {block!r})",
                  f"block({x}, {y + height}, {z}, {capst})"])


def stilt_base(x1, z1, x2, z2, y, post="spruce_log", beam="stripped_spruce_log", deck="spruce_planks", spacing=3, depth=16):
    """A raised floor on stilts for uneven ground or water: a plank deck at y over x1..x2, z1..z2, a log ring beam under
    its edges at y-1, and posts at the corners and every `spacing` blocks along the edges that go down from y-2 until
    they reach the ground (at most `depth` blocks). Build the house on the deck."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    posts = set()
    for xx in list(range(x1, x2 + 1, max(2, int(spacing)))) + [x2]:
        posts.update({(xx, z1), (xx, z2)})
    for zz in list(range(z1, z2 + 1, max(2, int(spacing)))) + [z2]:
        posts.update({(x1, zz), (x2, zz)})
    return _code([f"# stilt base x {x1}..{x2}, z {z1}..{z2}, deck at y={y}",
                  f"fill({x1}, {y}, {z1}, {x2}, {y}, {z2}, {deck!r})",
                  f"fill({x1}, {y - 1}, {z1}, {x2}, {y - 1}, {z1}, {_st(beam, axis='x')})",
                  f"fill({x1}, {y - 1}, {z2}, {x2}, {y - 1}, {z2}, {_st(beam, axis='x')})",
                  f"fill({x1}, {y - 1}, {z1 + 1}, {x1}, {y - 1}, {z2 - 1}, {_st(beam, axis='z')})",
                  f"fill({x2}, {y - 1}, {z1 + 1}, {x2}, {y - 1}, {z2 - 1}, {_st(beam, axis='z')})",
                  f"for px, pz in {sorted(posts)!r}:",
                  f"    yy = {y - 2}",
                  f"    while yy > {y - 2 - max(1, int(depth))} and is_air(px, yy, pz):",
                  f"        block(px, yy, pz, {_st(post, axis='y')})",
                  "        yy -= 1"])


def farm_plot(x, y, z, w=7, l=7, crop="wheat", fence="oak_fence", border="spruce_log"):
    """A fenced crop field: farmland at y-1 over w x l cells from the north-west corner (x, z), a water channel across
    the middle (on dirt at y-2), ripe `crop` (wheat, carrots, potatoes, beetroots), a log border under a fence with a
    gate in the middle of the south side and lanterns on the north corners. Keep w and l at 9 or less."""
    w, l = max(3, int(w)), max(3, int(l))
    if w > 9 or l > 9:
        raise ValueError("keep a plot to 9 x 9 or smaller so the water reaches every crop (use more plots)")
    age = 3 if crop == "beetroots" else 7
    wz = z + l // 2
    return _code([f"# farm plot {w} x {l} of {crop}",
                  f"fill({x - 1}, {y - 1}, {z - 1}, {x + w}, {y - 1}, {z + l}, {_st(border, axis='x')})",
                  f"fill({x}, {y - 1}, {z}, {x + w - 1}, {y - 1}, {z + l - 1}, {_st('farmland', moisture=7)})",
                  f"fill({x}, {y - 2}, {wz}, {x + w - 1}, {y - 2}, {wz}, 'dirt')",
                  f"fill({x}, {y - 1}, {wz}, {x + w - 1}, {y - 1}, {wz}, 'water')",
                  f"fill({x}, {y}, {z}, {x + w - 1}, {y}, {z + l - 1}, {_st(crop, age=age)})",
                  f"fill({x}, {y}, {wz}, {x + w - 1}, {y}, {wz}, 'air')",
                  f"fill({x - 1}, {y}, {z - 1}, {x + w}, {y}, {z - 1}, {fence!r})",
                  f"fill({x - 1}, {y}, {z + l}, {x + w}, {y}, {z + l}, {fence!r})",
                  f"fill({x - 1}, {y}, {z}, {x - 1}, {y}, {z + l - 1}, {fence!r})",
                  f"fill({x + w}, {y}, {z}, {x + w}, {y}, {z + l - 1}, {fence!r})",
                  f"block({x + w // 2}, {y}, {z + l}, {_st(fence + '_gate', facing='south', open=False)})",
                  f"block({x - 1}, {y}, {z - 1}, {_st(border, axis='y')})",
                  f"block({x + w}, {y}, {z - 1}, {_st(border, axis='y')})",
                  f"block({x - 1}, {y + 1}, {z - 1}, {_st('lantern', hanging=False)})",
                  f"block({x + w}, {y + 1}, {z - 1}, {_st('lantern', hanging=False)})"])


def fence_garden(x1, z1, x2, z2, y, fence="oak_fence", gates=("south",), flowers=("poppy", "dandelion", "cornflower", "allium"),
                 path_block="dirt_path"):
    """A fenced garden on grass: grass at y-1 over x1..x2, z1..z2 (dirt under it), a fence ring at y with a gate in the
    middle of each side in `gates`, a path of `path_block` from every gate to the middle, flower rows and leaf bushes."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    if x2 - x1 < 4 or z2 - z1 < 4:
        raise ValueError("a garden needs at least 5 x 5 blocks")
    cx, cz = (x1 + x2) // 2, (z1 + z2) // 2
    out = [f"# fenced garden x {x1}..{x2}, z {z1}..{z2}",
           f"fill({x1}, {y - 2}, {z1}, {x2}, {y - 2}, {z2}, 'dirt')",
           f"fill({x1}, {y - 1}, {z1}, {x2}, {y - 1}, {z2}, 'grass_block')",
           f"fill({x1}, {y}, {z1}, {x2}, {y}, {z1}, {fence!r})",
           f"fill({x1}, {y}, {z2}, {x2}, {y}, {z2}, {fence!r})",
           f"fill({x1}, {y}, {z1 + 1}, {x1}, {y}, {z2 - 1}, {fence!r})",
           f"fill({x2}, {y}, {z1 + 1}, {x2}, {y}, {z2 - 1}, {fence!r})"]
    gate_at = {"north": (cx, z1), "south": (cx, z2), "west": (x1, cz), "east": (x2, cz)}
    path = set()
    for g in gates or ():
        g = str(g).lower()
        if g not in gate_at:
            raise ValueError(f"gate side must be north, south, east or west (got {g!r})")
        gx, gz = gate_at[g]
        out.append(f"block({gx}, {y}, {gz}, {_st(fence + '_gate', facing=g, open=False)})")
        dx, dz = DIRS[OPP[g]]
        px_, pz_ = gx + dx, gz + dz
        while x1 < px_ < x2 and z1 < pz_ < z2:
            path.add((px_, pz_))
            if (px_, pz_) == (cx, cz):
                break
            px_, pz_ = px_ + dx, pz_ + dz
    for (px_, pz_) in sorted(path):
        out.append(f"block({px_}, {y - 1}, {pz_}, {path_block!r})")
    fl = list(flowers or ("poppy",))
    i = 0
    for xx in range(x1 + 1, x2):
        for zz in range(z1 + 1, z2):
            if (xx, zz) in path:
                continue
            if xx in (x1 + 1, x2 - 1) and zz in (z1 + 1, z2 - 1):
                out.append(f"block({xx}, {y}, {zz}, {_st('oak_leaves', persistent=True)})")
            elif (xx + zz) % 2 == 0:
                out.append(f"block({xx}, {y}, {zz}, {fl[i % len(fl)]!r})")
                i += 1
    return _code(out)


def site(x1, z1, x2, z2, y, top="grass_block", under="dirt"):
    """The ground plot a house stands on: `under` at y-1 and `top` at y over x1..x2, z1..z2. Build the house's
    foundation at y (it replaces the grass) and the rest on top."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    return _code([f"# ground plot x {x1}..{x2}, z {z1}..{z2}",
                  f"fill({x1}, {y - 1}, {z1}, {x2}, {y - 1}, {z2}, {under!r})",
                  f"fill({x1}, {y}, {z1}, {x2}, {y}, {z2}, {top!r})"])


# Road builder (round 5): the hill town had path blocks with ground or blocks right on top of them - streets cut into
# the slope without clearing above. A road now clears the room above every cell, fills the gap under it and takes a
# half step (a bottom slab) where it rises, so it can follow the ground.
ROAD_SKIP = ("air", "cave_air", "void_air", "light", "water", "lava", "short_grass", "tall_grass", "fern", "large_fern",
             "dead_bush", "snow", "vine", "poppy", "dandelion", "azure_bluet", "oxeye_daisy", "cornflower", "allium",
             "lily_of_the_valley", "blue_orchid", "pink_petals", "azalea", "flowering_azalea", "sweet_berry_bush",
             "moss_carpet", "glow_lichen", "bamboo", "sugar_cane", "seagrass", "kelp", "lily_pad", "wildflowers",
             "leaf_litter", "bush", "firefly_bush", "short_dry_grass", "tall_dry_grass")
ROAD_SKIP_END = ("_leaves", "_log", "_wood", "_sapling", "_tulip", "_carpet", "_flower", "_mushroom", "_roots",
                 "_fungus", "_bush", "_vines", "_vine", "torch", "lantern", "_sign", "_banner", "_button",
                 "_pressure_plate", "_fence", "_fence_gate", "_wall", "_pane", "_door", "_trapdoor", "rail")


# The height profile of a road, as source: road() uses it on given heights and writes it into the build script for
# heights read from the ground there. At most 1 block up in 2 cells (the middle of the highest and the lowest profile
# that keep it; a profile that keeps it already is unchanged) through the given heights (`fixed`, where they fit) with a
# flat landing round every corner (where it fits), so the cells round a corner (they belong to centre cells a few
# apart) never step up twice in a row.
ROAD_PROFILE = """def road_profile(ry, corners, ext, fixed):
    n_ = len(ry)
    cap = lambda k: (k + 1) // 2
    up = [min(ry[j] + cap(abs(i - j)) for j in range(n_)) for i in range(n_)]
    lo = [max(ry[j] - cap(abs(i - j)) for j in range(n_)) for i in range(n_)]
    mid = [(up[i] + lo[i]) // 2 for i in range(n_)]
    pins = {0: mid[0], n_ - 1: mid[n_ - 1]}
    for j, v in sorted(fixed.items()):
        if all(abs(v - pv) <= cap(abs(j - pj)) for pj, pv in pins.items() if pj != j):
            pins[j] = v
    for c in corners:
        zone = [j for j in range(max(1, c - ext), min(n_ - 1, c + ext + 1)) if j not in pins or j == c]
        if not zone:
            continue
        others = {pj: pv for pj, pv in pins.items() if pj not in zone}
        hi = min([pv + cap(abs(j - pj)) for j in zone for pj, pv in others.items()] + [10 ** 6])
        lw = max([pv - cap(abs(j - pj)) for j in zone for pj, pv in others.items()] + [-10 ** 6])
        if lw <= hi:
            v = min(max(pins.get(c, mid[c]), lw), hi)
            for j in zone:
                pins[j] = v
    out = []
    for i in range(n_):
        hi = min(pv + cap(abs(i - pj)) for pj, pv in pins.items())
        lw = max(pv - cap(abs(i - pj)) for pj, pv in pins.items())
        out.append(min(max(mid[i], lw), hi))
    return out
"""
_ns = {}
exec(ROAD_PROFILE, _ns)
_road_profile = _ns["road_profile"]


ROAD_LAND = ("dirt", "grass_block", "stone", "andesite", "diorite", "granite", "tuff", "gravel", "coarse_dirt", "podzol",
             "rooted_dirt", "deepslate", "sand", "red_sand", "snow_block", "powder_snow", "calcite", "moss_block", "clay",
             "mud", "ice", "packed_ice", "blue_ice", "mycelium", "mossy_cobblestone", "cobblestone", "dripstone_block",
             "smooth_basalt", "basalt", "terracotta")
PATH_LIKE = ("dirt_path", "stone_bricks", "polished_andesite", "packed_mud", "stone_brick_slab", "cobblestone_slab",
             "mossy_cobblestone_slab", "polished_andesite_slab", "mud_brick_slab", "mud_bricks", "bricks", "brick_slab",
             "smooth_stone", "smooth_stone_slab")     # built paths and squares (not gravel or cobble: the land has those)


def _road_cells(pts, width):
    """(centre line [(x, z)] in order, {column: (distance, centre index)}) of a road through pts, `width` wide."""
    centre = []
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        n = max(abs(bx - ax), abs(bz - az), 1)
        for i in range(n + 1):
            c = (ax + round((bx - ax) * i / n), az + round((bz - az) * i / n))
            if not centre or centre[-1] != c:
                centre.append(c)
    lo = -((width - 1) // 2)
    cols = {}
    for k, (cx, cz) in enumerate(centre):
        for w in range(lo, lo + width):
            for c in ((cx + w, cz), (cx, cz + w)):
                d = abs(w)
                if c not in cols or d < cols[c][0]:
                    cols[c] = (d, k)
    return centre, cols


def road(points, y=None, width=3, block="dirt_path", under="dirt", step="cobblestone_slab", clear=3):
    """A street or garden path through `points` ([[x, z], ...] or [[x, z, y], ...], at least 2), `width` wide,
    straight or diagonal between the points: `block` on top with `under` below it, `clear` blocks of air cleared over
    every cell (no ground, wall or leaves left on the path) and the gap under it filled with `under` down to the ground.
    Heights: with `y` given, the road is flat at y (or a straight slope between points given as [x, z, y]); with
    y=None it FOLLOWS THE GROUND (the top ground block of each centre cell, trees and plants skipped) and passes
    through the heights of the [x, z, y] points, smoothed to rise at most 1 block in 2 with flat landings at corners. Where the road rises by 1 the higher
    cells get a bottom `step` slab (a half step, no jump). Several points make it bend; follow the ground and the
    houses instead of one straight line. A climb steeper than 1 in 2 needs straight_stair_run between two flat parts.
    The streets of plan_layout: road(the street's corner points [[x, z, y], ...], width=street width)."""
    raw = [p for p in points or [] if isinstance(p, (list, tuple)) and len(p) in (2, 3)]
    if len(raw) < 2 or len(raw) != len(points or []):
        raise ValueError("a road needs at least 2 points [x, z] or [x, z, y]")
    pts = [(int(p[0]), int(p[1])) for p in raw]
    hs = [int(p[2]) if len(p) == 3 else (None if y is None else int(y)) for p in raw]
    width, clear = max(1, int(width)), max(2, int(clear))
    centre, cols = _road_cells(pts, width)
    # heights along the centre line: with y given, straight slopes between the point heights (flat at y); with y=None
    # the ground there, held at the points' own heights
    known = {}
    for (ax, az), (bx, bz), ha, hb in zip(pts, pts[1:], hs, hs[1:]):
        n = max(abs(bx - ax), abs(bz - az), 1)
        for i in range(n + 1):
            c = (ax + round((bx - ax) * i / n), az + round((bz - az) * i / n))
            if ha is not None and hb is not None:
                known.setdefault(c, ha + round((hb - ha) * i / n))
            elif i == 0 and ha is not None:
                known.setdefault(c, ha)
            elif i == n and hb is not None:
                known[c] = hb
    given = [known.get(c) for c in centre] if y is not None else [None] * len(centre)
    follows = any(v is None for v in given)
    corners = [i for i in range(1, len(centre) - 1) if (centre[i][0] - centre[i - 1][0], centre[i][1] - centre[i - 1][1])
               != (centre[i + 1][0] - centre[i][0], centre[i + 1][1] - centre[i][1])]
    ext = width // 2 + 1
    at = {c: i for i, c in enumerate(centre)}
    fixed = {at[pt]: hv for pt, hv in zip(pts, hs) if hv is not None and pt in at}   # the points' own heights
    if not follows:
        given = _road_profile(given, corners, ext, fixed)
    out = [f"# road through {len(pts)} points, {width} wide, {clear} clear above"
           + (", following the ground" if follows else ""),
           f"rc = {centre!r}",
           f"ry = {given!r}",
           f"rk = {dict((c, k) for c, (_d, k) in sorted(cols.items()))!r}"]
    out.append(f"skip, skip_end = {ROAD_SKIP!r}, {ROAD_SKIP_END!r}")
    out.append(f"land = {ROAD_LAND!r}")
    if follows:
        out += ["top = bounds()[4] + 1",
                "def ground_at(x, z):",
                "    for yy in range(top, top - 400, -1):",
                "        st = get(x, yy, z)",
                "        if st is None:",
                "            continue",
                "        n = st.split('[')[0].replace('minecraft:', '')",
                "        if n in skip or n.endswith(skip_end):",
                "            continue",
                "        return yy",
                "    return None",
                "ry = [v if v is not None else ground_at(x, z) for v, (x, z) in zip(ry, rc)]",
                "have = [v for v in ry if v is not None]",
                "base = have[0] if have else 0",
                "for i in range(len(ry)):",
                "    if ry[i] is None:",
                "        ry[i] = ry[i - 1] if i else base",
                ROAD_PROFILE.rstrip(),
                f"ry = road_profile(ry, {corners!r}, {ext}, {fixed!r})"]
    out += ["tree_cut = []",
            "for (x, z), k in rk.items():",
            "    h = ry[k]",
            f"    for yy in range(h + 1, h + {clear} + 1):",
            "        st = get(x, yy, z)",
            "        if st and st.split('[')[0].endswith(('_log', '_wood', '_leaves')):",
            "            tree_cut.append((x, yy, z))",
            "near4 = lambda x, z: ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1))",
            "for (x, z), k in rk.items():                  # loose gravel at the road's edge becomes plain ground",
            "    h = ry[k]",
            "    for c in near4(x, z):",
            "        if c not in rk:",
            "            for yy in range(h + 2, h - 9, -1):",
            "                st = get(c[0], yy, c[1])",
            "                if st and st.split('[')[0].replace('minecraft:', '') in ('gravel', 'coarse_dirt'):",
            f"                    block(c[0], yy, c[1], {under!r})",
            f"pathlike = {sorted(set(PATH_LIKE) | {block, step}) !r}",
            "def surface(c, yy):",
            "    st = get(c[0], yy, c[1])",
            "    return bool(st) and st.split('[')[0].replace('minecraft:', '') in pathlike and get(c[0], yy + 1, c[1]) is None",
            "for (x, z), k in rk.items():",
            "    h = ry[k]",
            "    low = any((ry[rk[c]] == h - 1) if c in rk else surface(c, h - 1) for c in near4(x, z))",
            f"    clear(x, h + 1, z, x, h + {clear}, z)",
            f"    yy = h + {clear + 1}                          # a deep cut is open to the sky: ground, snow, plants and",
            "    while yy < h + 96:                             # trees left over the road would hang there or float",
            "        st = get(x, yy, z)",
            "        n = st.split('[')[0].replace('minecraft:', '') if st else ''",
            "        if not n or n in ('water', 'lava') or not (n in land or n in skip or n.endswith(skip_end)):",
            "            break",
            "        if n.endswith(('_log', '_wood', '_leaves')):",
            "            tree_cut.append((x, yy, z))",
            "        block(x, yy, z, 'air')",
            "        yy += 1",
            f"    block(x, h, z, B({step!r}, type='bottom') if low else {block!r})",
            "    below = get(x, h - 1, z)",
            "    nb = below.split('[')[0].replace('minecraft:', '') if below else ''",
            "    filled = not nb or nb in skip or nb.endswith(skip_end)",
            "    if filled:                                     # keep solid ground under the road as it is",
            f"        block(x, h - 1, z, {under!r})",
            "    d = h - 2",
            "    while filled and d > h - 20 and get(x, d, z) is None:",
            f"        block(x, d, z, {under!r})",
            "        d -= 1",
            "    if filled:                                     # loose gravel the fill now covers becomes ground too",
            "        while d > h - 30 and (get(x, d, z) or '').split('[')[0].replace('minecraft:', '') in ('gravel', 'coarse_dirt'):",
            f"            block(x, d, z, {under!r})",
            "            d -= 1",
            "for (x, z), k in rk.items():                  # a street or square met 1 higher gets a half step at its edge",
            "    h = ry[k]",
            "    if (get(x, h, z) or '').split('[')[0].endswith('_slab'):",
            "        continue",
            "    for c in near4(x, z):",
            "        st = get(c[0], h + 1, c[1])",
            "        if c not in rk and surface(c, h + 1) and not st.split('[')[0].endswith(('_slab', '_stairs')):",
            f"            block(c[0], h + 1, c[1], B({step!r}, type='bottom'))",
            "# what is left of a tree cut by the road: a crown that no longer touches the ground or a building goes too",
            "def tree_part(st):",
            "    return bool(st) and st.split('[')[0].endswith(('_log', '_wood', '_leaves'))",
            "near6 = lambda x, y, z: ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1))",
            "done = set()",
            "for c in tree_cut:",
            "    for s0 in near6(*c):",
            "        if s0 in done or not tree_part(get(*s0)):",
            "            continue",
            "        group, todo, held = {s0}, [s0], False",
            "        while todo and not held and len(group) < 3000:",
            "            for q in near6(*todo.pop()):",
            "                if q in group:",
            "                    continue",
            "                st = get(*q)",
            "                if tree_part(st):",
            "                    group.add(q)",
            "                    todo.append(q)",
            "                elif st and st.split('[')[0].replace('minecraft:', '') not in skip:",
            "                    held = True                  # still on the ground or a building",
            "                    break",
            "        done |= group",
            "        if not held and not todo:",
            "            for q in group:",
            "                block(q[0], q[1], q[2], 'air')"]
    return _code(out)


def plaza(x1, z1, x2, z2, y, block="stone_bricks", well=True):
    """A paved square: `block` at y over x1..x2, z1..z2 (dirt under it) with a roofed well in the middle when `well`
    and a lantern on a post at each corner. Make it 7 x 7 or bigger so it reads as a square, not a road."""
    x1, x2 = sorted((x1, x2))
    z1, z2 = sorted((z1, z2))
    if x2 - x1 < 4 or z2 - z1 < 4:
        raise ValueError("a plaza needs at least 5 x 5 blocks")
    cx, cz = (x1 + x2) // 2, (z1 + z2) // 2
    out = [f"# plaza x {x1}..{x2}, z {z1}..{z2}",
           f"fill({x1}, {y - 1}, {z1}, {x2}, {y - 1}, {z2}, 'dirt')",
           f"fill({x1}, {y}, {z1}, {x2}, {y}, {z2}, {block!r})"]
    for (px, pz) in ((x1, z1), (x1, z2), (x2, z1), (x2, z2)):
        out += [f"fill({px}, {y + 1}, {pz}, {px}, {y + 2}, {pz}, {_st('spruce_log', axis='y')})",
                f"block({px}, {y + 3}, {pz}, {_st('lantern', hanging=False)})"]
    if well and x2 - x1 >= 6 and z2 - z1 >= 6:
        out += [f"fill({cx - 1}, {y - 2}, {cz - 1}, {cx + 1}, {y - 1}, {cz + 1}, 'cobblestone')",
                f"fill({cx - 1}, {y}, {cz - 1}, {cx + 1}, {y}, {cz + 1}, 'cobblestone')",
                f"block({cx}, {y}, {cz}, 'water')",
                f"block({cx}, {y - 1}, {cz}, 'water')"]
        for (px, pz) in ((cx - 1, cz - 1), (cx - 1, cz + 1), (cx + 1, cz - 1), (cx + 1, cz + 1)):
            out.append(f"fill({px}, {y + 1}, {pz}, {px}, {y + 2}, {pz}, 'cobblestone_wall')")
        out.append(f"fill({cx - 1}, {y + 3}, {cz - 1}, {cx + 1}, {y + 3}, {cz + 1}, {_st('spruce_slab', type='bottom')})")
    return _code(out)


# ------------------------------------------------------------------ shape: a manor that is not one long box
_TURN = {"south": ((1, 0), (0, 1)), "north": ((-1, 0), (0, -1)), "east": ((0, -1), (1, 0)), "west": ((0, 1), (-1, 0))}


class _Frame:
    """Local coordinates for a part that faces `facing`: local +lz is the front (out of the entrance), local +lx runs
    along the front. at(lx, lz) -> world (x, z); side('south') -> the world side that local south (the front) is."""

    def __init__(self, x, z, facing):
        _dir(facing)
        self.x, self.z = int(x), int(z)
        self.ex, self.ez = _TURN[facing]                             # world vectors of local +lx and +lz

    def at(self, lx, lz):
        return (self.x + self.ex[0] * lx + self.ez[0] * lz, self.z + self.ex[1] * lx + self.ez[1] * lz)

    def side(self, name):
        v = {"south": (0, 1), "north": (0, -1), "east": (1, 0), "west": (-1, 0)}[name]
        w = (self.ex[0] * v[0] + self.ez[0] * v[1], self.ex[1] * v[0] + self.ez[1] * v[1])
        return next(n for n, d in DIRS.items() if d == w)

    def rect(self, lx1, lz1, lx2, lz2):
        (a, b), (c, d) = self.at(lx1, lz1), self.at(lx2, lz2)
        return min(a, c), min(b, d), max(a, c), max(b, d)

    def axis(self, local_axis):
        """'x' or 'z' in the world for a local ridge axis."""
        return local_axis if self.ex[0] else ("z" if local_axis == "x" else "x")

    def run(self, l1, l2, lz):
        """The world cell of the west/north end of the local run lx l1..l2 on row lz (windows and balconies count their
        width east or south from there)."""
        return min(self.at(l1, lz), self.at(l2, lz))


def _roof_cells(x1, z1, x2, z2, y, stairs, trim, ridge, overhang=2, fill="oak_planks", open_end=None):
    """The cells of one trimmed gable roof (gable_roof_trim without the clean-up), to merge with others."""
    a = _gable_args(x1, z1, x2, z2, ridge, open_end)
    return _gable_cells(*a[:4], y, _stairs(stairs), _stairs(trim), a[4], max(0, int(overhang)), fill, a[5])


def _merge_roofs(parts, cut=()):
    """Several roofs as one: {cell: state}, the later roof wins a shared cell, cells over the columns in `cut` (the
    rectangles of a taller block the roof runs into) are dropped."""
    cells = {}
    for part in parts:
        cells.update(part)
    for (x1, z1, x2, z2) in cut:
        for key in [p for p in cells if x1 <= p[0] <= x2 and z1 <= p[2] <= z2]:
            del cells[key]
    return cells


def bay_window(x, y, z, facing, width=3, floors=1, storey=4, depth=1, wall=None, frame="oak_log", roof=ROOF_DEFAULT,
               glass="glass_pane", box="oak_trapdoor"):
    """A bay window standing out of a wall: `width` (3 or 5) wide, `depth` blocks out (1 or 2) on the `facing` side of a
    wall whose outside face is the row at (x, z) (x, z is the middle of the bay, on the wall line); log posts on the
    corners, glass panes on the front and sides of every floor (`floors` of `storey` free blocks from y), a floor slab
    and a small pent roof of `roof` stairs on top. The wall behind it is opened into the bay. It breaks a long flat
    wall into shorter runs. wall = the fill (default: birch planks, the light look)."""
    dx, dz = _dir(facing)
    px, pz = (1, 0) if _AXIS[facing] == "x" else (0, 1)
    width = 5 if int(width) >= 5 else 3
    depth = 2 if int(depth) >= 2 else 1
    floors, storey = max(1, int(floors)), max(3, int(storey))
    fill = wall or WALL_STYLES[DEFAULT_STYLE][0]
    half = width // 2
    top = y + floors * (storey + 1) - 1
    rst = _stairs(roof)
    conn = {"east": True, "west": True} if px else {"north": True, "south": True}
    side_conn = {"north": True, "south": True} if px else {"east": True, "west": True}

    def at(k, w):
        return x + dx * k + px * w, z + dz * k + pz * w
    out = [f"# bay window facing {facing}, {width} wide, {depth} out, {floors} floor(s)"]
    for k in range(1, depth + 1):                                    # the floor of the bay, on a stone foot
        for w in range(-half, half + 1):
            cx, cz = at(k, w)
            out.append(f"block({cx}, {y - 1}, {cz}, 'cobblestone')")
    for f in range(floors):
        fy = y + f * (storey + 1)
        for w in range(-half + 1, half):                             # open the wall behind
            cx, cz = at(0, w)
            out.append(f"fill({cx}, {fy}, {cz}, {cx}, {fy + storey - 1}, {cz}, 'air')")
        for k in range(1, depth + 1):
            for w in range(-half, half + 1):
                cx, cz = at(k, w)
                corner = abs(w) == half
                if corner and k == depth:
                    out.append(f"fill({cx}, {fy}, {cz}, {cx}, {fy + storey}, {cz}, {_st(frame, axis='y')})")
                    continue
                if corner:
                    st = _st(glass, **side_conn) if glass.endswith("_pane") else repr(glass)
                elif k == depth:
                    st = _st(glass, **conn) if glass.endswith("_pane") else repr(glass)
                else:
                    st = "'air'"
                out.append(f"block({cx}, {fy}, {cz}, {fill!r})")
                if st != "'air'":
                    out.append(f"fill({cx}, {fy + 1}, {cz}, {cx}, {fy + storey - 2}, {cz}, {st})")
                    out.append(f"block({cx}, {fy + storey - 1}, {cz}, {fill!r})")
                else:
                    out.append(f"fill({cx}, {fy + 1}, {cz}, {cx}, {fy + storey - 1}, {cz}, 'air')")
                out.append(f"block({cx}, {fy + storey}, {cz}, {_st(frame, axis=_AXIS[facing])})")
        if f == 0:
            for w in range(-half + 1, half):                         # a flower box under the front panes
                cx, cz = at(depth + 1, w)
                out.append(f"block({cx}, {fy}, {cz}, {_st(box, facing=facing, half='top', open=False)})")
    for k in range(1, depth + 2):                                    # pent roof: stairs rising to the wall
        for w in range(-half - 1, half + 2):
            cx, cz = at(k, w)
            if k == depth + 1 or abs(w) == half + 1:
                out.append(f"block({cx}, {top + 1}, {cz}, {_st(rst[:-7] + '_slab', type='bottom')})")
            else:
                out.append(f"block({cx}, {top + 1}, {cz}, {_st(rst, facing=OPP[facing], half='bottom')})")
    return _code(out)


def dormer(x, y, z, facing, width=3, roof=ROOF_DEFAULT, trim=TRIM_DEFAULT, wall=None, glass="glass_pane"):
    """A dormer on a roof slope: a small gabled box `width` (3 or 5) wide whose window wall faces `facing` (down the
    slope), the window wall's middle at (x, y, z) with y the lowest glass row (on the roof stairs, the slope rising
    behind it). Glass in the middle, birch fill round it, a trimmed gable roof with its own ridge running into the main
    roof. It breaks a long roof plane and adds a peak to the outline."""
    dx, dz = _dir(facing)
    px, pz = (1, 0) if _AXIS[facing] == "x" else (0, 1)
    width = 5 if int(width) >= 5 else 3
    half = width // 2
    fill = wall or WALL_STYLES[DEFAULT_STYLE][0]
    conn = {"east": True, "west": True} if px else {"north": True, "south": True}

    def at(k, w):
        return x - dx * k + px * w, z - dz * k + pz * w               # k counts back up the slope
    out = [f"# dormer facing {facing}, {width} wide"]
    depth = half + 2
    for k in range(depth):
        for w in range(-half, half + 1):
            cx, cz = at(k, w)
            out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + 1}, {cz}, {fill!r})")
            if k and abs(w) < half:
                out.append(f"fill({cx}, {y}, {cz}, {cx}, {y + 1}, {cz}, 'air')")
    for w in range(-half + 1, half):
        cx, cz = at(0, w)
        out.append(f"fill({cx}, {y}, {cz}, {cx}, {y + 1}, {cz}, "
                   f"{_st(glass, **conn) if glass.endswith('_pane') else repr(glass)})")
    (ax, az), (bx, bz) = at(0, -half), at(depth - 1, half)
    ridge = "z" if px else "x"
    cells = _roof_cells(min(ax, bx), min(az, bz), max(ax, bx), max(az, bz), y + 2, roof, trim, ridge, overhang=0,
                        fill=fill, open_end=OPP[facing])
    return _code(out + _emit(_settle(cells, _full(_stairs(trim)))))


def manor_layout(x, y, z, facing="south", style="light", roof=ROOF_DEFAULT, trim=TRIM_DEFAULT, raised=4, stilts=False,
                 ground=None, flower=None, chimney_block="bricks"):
    """A whole manor in the shape of the reference houses, not one long box: a taller central block (17 x 11, 3 storeys
    of 5, its big gable facing the front) with a 3-storey entrance bay standing 3 out of the middle of the front (a lower
    gable in front of the big one) and a 2-storey bay at the back, two 2-storey wings (9 x 9, set back 3, their own
    front gables 12 lower than the central ridge) stepping down on both sides, a porch at the door and a grand front
    stair in flights with landings up to it, a balcony with a door on each wing, 2 x 2 framed windows (planters of soft
    mixed plants under every second window of the ground and first floor, trapdoor sills under the rest, in the
    frame's wood; `flower` = one plant or a list instead of the mix), storey bands and a chimney. No straight wall is
    longer than 9 blocks.
    (x, z) is the middle of the central block, y the ground level (the top of the ground is y-1), `facing` the entrance
    side. The house stands `raised` blocks up (1-8) on a stone terrace with railings, or on log stilts down to the ground
    (stilts=True, for uneven ground or water: the posts go down until they meet the ground; `ground` = the lowest
    ground top under the house, default y-1). Footprint about 35 x 33 round (x, z) with the stair; top about
    y + raised + 29. Palette: style / roof / trim as for framed_house and gable_roof_trim (default birch fill in oak logs,
    teal roofs with an oak trim)."""
    F = _Frame(x, z, facing)
    raised = max(1, min(8, int(raised)))
    y = int(y)
    Y = y + raised                                                   # ground floor walls start here
    S, SW = 5, 4                                                     # storey of the central block and of the wings
    fill, frame = _style(style, None, None)
    low = int(ground) if ground is not None else y - 1
    sd = F.side
    W = dict(width=2, height=2, flower=flower, box=trapdoor_of(frame))
    out = [f"# manor layout facing {facing} round x {x}, z {z}: central block, entrance bay, two stepped wings, "
           f"grand stair\n"]
    n_win = [0]

    def planter(wy):
        """Every second window of the ground and first floor gets a planter; the others and the top floor a sill."""
        n_win[0] += 1
        return wy <= Y + 1 + S + 1 and n_win[0] % 2 == 1

    def win(l1, l2, wy, lz, n, **kw):
        a = dict(W, **kw)
        a["width"] = abs(l2 - l1) + 1
        wx, wz = F.run(l1, l2, lz)
        return window_with_box(wx, wy, wz, sd(n), planter=planter(wy), **a)

    def win_side(lz1, lz2, wy, lx, n):
        wx, wz = min(F.at(lx, lz1), F.at(lx, lz2))
        return window_with_box(wx, wy, wz, sd(n), planter=planter(wy), **dict(W, width=abs(lz2 - lz1) + 1))

    def line(lx1, lz1, lx2, lz2, yy, st):
        x1, z1, x2, z2 = F.rect(lx1, lz1, lx2, lz2)
        return f"fill({x1}, {yy}, {z1}, {x2}, {yy}, {z2}, {st!r})\n"
    # ---- the base: a stone terrace (or a deck on stilts) under the house, the front terrace and the wing terraces
    for r in ((-9, -9, 9, 11), (-17, -7, 17, 5)):
        x1, z1, x2, z2 = F.rect(*r)
        if stilts:
            out.append(stilt_base(x1, z1, x2, z2, Y - 1, depth=max(2, Y - low)))
        else:
            out.append(f"fill({x1}, {low + 1}, {z1}, {x2}, {Y - 2}, {z2}, 'stone_bricks')\n"
                       f"fill({x1}, {Y - 1}, {z1}, {x2}, {Y - 1}, {z2}, 'spruce_planks')\n")
    for sgn in (1, -1):                                              # railings round the terrace edges
        for r in ((10, 5, 17, 5), (17, -7, 17, 4), (9, 6, 9, 11), (3, 11, 8, 11), (9, -9, 9, -8), (4, -9, 8, -9),
                  (10, -7, 16, -7)):
            out.append(line(r[0] * sgn, r[1], r[2] * sgn, r[3], Y, "oak_fence"))
    # ---- bodies: central block, entrance bay, back bay, wings
    out.append(framed_house(*F.rect(-8, -5, 8, 5), Y, floors=3, storey=S, fill=fill, frame=frame, spacing=8,
                            flat=[sd("east"), sd("west")]))
    out.append(framed_house(*F.rect(-3, 5, 3, 8), Y, floors=3, storey=S, fill=fill, frame=frame, spacing=6,
                            skip=[sd("north")], flat=[sd("east"), sd("west")], clear=True))
    out.append(framed_house(*F.rect(-3, -8, 3, -5), Y, floors=2, storey=S, fill=fill, frame=frame, spacing=6,
                            skip=[sd("south")], flat=[sd("east"), sd("west")], clear=True))
    for sgn in (1, -1):
        out.append(framed_house(*F.rect(8 * sgn, -6, 16 * sgn, 2), Y, floors=2, storey=SW, fill=fill, frame=frame,
                                spacing=8, skip=[sd("west" if sgn > 0 else "east")], clear=True))
    for f in range(3):                                               # the central block opens into the bays
        fy = Y + f * (S + 1)
        for lz in ((5, -5) if f < 2 else (5,)):
            x1, z1, x2, z2 = F.rect(-2, lz, 2, lz)
            out.append(f"fill({x1}, {fy}, {z1}, {x2}, {fy + S - 1}, {z2}, 'air')\n")
    for sgn in (1, -1):                                              # doors from the central block into the wings
        wx, wz = F.at(8 * sgn, -2)
        f = sd("east" if sgn > 0 else "west")
        out.append(f"block({wx}, {Y}, {wz}, {_st('oak_door', facing=f, half='lower', hinge='left', open=False)})\n"
                   f"block({wx}, {Y + 1}, {wz}, {_st('oak_door', facing=f, half='upper', hinge='left', open=False)})\n")
    # ---- windows: 2 x 2 with shutters and a flower box; a tall 3-wide window over the porch
    for f in range(3):
        wy = Y + 1 + f * (S + 1)
        for l1 in (-6, 5):
            out.append(win(l1, l1 + 1, wy, 5, "south"))
            if f < 2:                                                # the top floor's back is under the bay's eaves
                out.append(win(l1, l1 + 1, wy, -5, "north"))
        if f:
            out.append(win(-1, 1, wy, 8, "south", height=3))
        if f < 2:
            out.append(win(-1, 1, wy, -8, "north"))
    for sgn in (1, -1):
        for f in range(2):
            wy = Y + 1 + f * (SW + 1)
            for l1 in ((10, 13) if sgn > 0 else (-11, -14)):
                if not f:
                    out.append(win(l1, l1 + 1, wy, 2, "south"))
                out.append(win(l1, l1 + 1, wy, -6, "north"))
            for lz1 in (-4, -1):
                out.append(win_side(lz1, lz1 + 1, wy, 16 * sgn, "east" if sgn > 0 else "west"))
    # ---- storey bands: the central block's front, the wing backs and ends
    for yy in (Y + S, Y + 2 * S + 1):
        out.append(storey_band(*F.rect(-8, -5, 8, 5), yy, skip=[sd("east"), sd("west"), sd("north")],
                               gaps=[F.rect(-4, 6, 4, 8)]))
    for sgn in (1, -1):
        out.append(storey_band(*F.rect(8 * sgn, -6, 16 * sgn, 2), Y + SW,
                               skip=[sd("south"), sd("west" if sgn > 0 else "east")],
                               gaps=[F.rect(6 * sgn, -8, 7 * sgn, -8)]))
    # ---- porch at the front door, the grand stair up to it, a balcony on each wing
    px, pz = F.at(0, 8)
    out.append(porch(px, Y, pz, sd("south"), width=5, depth=3, path=0))
    flight = 2 if raised > 2 else raised
    length = raised + 2 * (-(-raised // flight))
    sx, sz = F.at(-1, 12 + length - 1)
    out.append(external_stair(sx, y, sz, sd("north"), raised, width=3, flight=flight, landing=2))
    for sgn in (1, -1):
        bx, bz = F.run(10 * sgn, 14 * sgn, 3)
        out.append(balcony(bx, Y + SW, bz, sd("south"), length=5, depth=2, door=True))
    # ---- roofs, merged so the joins are clean: wings first (cut at the central block), then the central block
    rs, tr = _stairs(roof), _stairs(trim)
    wings = [_roof_cells(*F.rect(8 * sgn, -6, 16 * sgn, 2), Y + 2 * (SW + 1), rs, tr, F.axis("z"), 2, fill)
             for sgn in (1, -1)]
    cells = _merge_roofs(wings, cut=[F.rect(-8, -20, 8, 20)])
    cells.update(_merge_roofs([
        _roof_cells(*F.rect(-8, -5, 8, 5), Y + 3 * (S + 1), rs, tr, F.axis("z"), 1, fill),
        _roof_cells(*F.rect(-3, 5, 3, 8), Y + 3 * (S + 1), rs, tr, F.axis("z"), 2, fill, open_end=sd("north")),
        _roof_cells(*F.rect(-3, -8, 3, -5), Y + 2 * (S + 1), rs, tr, F.axis("z"), 2, fill, open_end=sd("south"))]))
    out.append(_code(["# manor roofs"] + _emit(_settle(cells, _full(tr)))))
    cx, cz = F.at(-5, -7)
    out.append(chimney(cx, Y - 1, cz, height=3 * (S + 1) + 10, block=chimney_block))
    return "".join(out)
