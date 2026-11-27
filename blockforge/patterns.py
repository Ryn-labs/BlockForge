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
