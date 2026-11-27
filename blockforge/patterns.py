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


def _stairs(name):
    name = str(name)
    return name if name.endswith("_stairs") else name + "_stairs"


def _st(name, **props):
    return "B(%r, %s)" % (name, ", ".join("%s=%r" % kv for kv in props.items()))


def _code(lines):
    return "\n".join(lines) + "\n"


def straight_stair_run(x, y, z, dir, length, width=3, block="stone_brick_stairs", support="stone", path="stone_bricks",
                       landing=2):
    """A straight climb: `length` bottom stairs facing uphill, rising 1 per cell from y, then `landing` flat path cells.

    The first stair is at (x, y, z); `width` cells wide to the right-hand side of the direction. Solid support below each
    step down to y-1."""
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
    return _code(out)


def switchback_landing(x, y, z, dir, length=4, width=2, block="stone_brick_stairs", support="stone", path="stone_bricks"):
    """Two stair runs joined by a flat landing: climb `length` steps along `dir`, turn on the landing, climb `length`
    more back the other way beside the first run (a stone wall separates them). Climbs 2*length blocks in total."""
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
    for off in range(L, L + depth):                                 # landing, same height as the last stair of run A
        for lat in range(2 * W + 1):
            cx, cz = cell(off, lat)
            out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + L - 2}, {cz}, {support!r})")
            out.append(f"block({cx}, {y + L - 1}, {cz}, {path!r})")
    back = OPP[dir]
    for j in range(L):                                              # run B climbs back toward the start
        for w in range(W):
            cx, cz = cell(L - 1 - j, W + 1 + w)
            out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + L + j - 1}, {cz}, {support!r})")
            out.append(f"block({cx}, {y + L + j}, {cz}, {_st(stairs, facing=back, half='bottom', shape='straight')})")
    for w in range(W):                                              # exit platform at the top of run B
        cx, cz = cell(-1, W + 1 + w)
        out.append(f"fill({cx}, {y - 1}, {cz}, {cx}, {y + 2 * L - 2}, {cz}, {support!r})")
        out.append(f"block({cx}, {y + 2 * L - 1}, {cz}, {path!r})")
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
