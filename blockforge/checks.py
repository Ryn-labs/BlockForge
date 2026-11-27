"""Build checks shared by the app and the AI: walkable paths, doors, floating parts.

run(blocks) takes {(x, y, z): "minecraft:state[props]"} and returns findings:
  {"check": name, "at": [x, y, z], "text": "plain sentence with coordinates", "count": n}
"count" is the true number of problems of that check (the list itself is capped per check).
"""
import collections

CAP = 25                                                   # findings kept per check; the rest are only counted

CHECK_LABELS = {
    "floating": "floating parts", "buried_path": "buried path", "jump_step": "jump step",
    "corner_turn": "corner turn", "wrong_facing": "wrong facing", "door_blocked": "blocked door",
    "headroom": "headroom",
}

DV = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}

# ---- solidity: a full cube you cannot stand inside. Anything not listed is treated as NOT solid
# (the checks should only flag what we are sure about).
SOLID_NAMES = {
    "stone", "cobblestone", "mossy_cobblestone", "dirt", "grass_block", "coarse_dirt", "rooted_dirt", "podzol", "mycelium",
    "sand", "red_sand", "gravel", "clay", "terracotta", "glass", "tinted_glass", "andesite", "diorite", "granite",
    "polished_andesite", "polished_diorite", "polished_granite", "deepslate", "cobbled_deepslate", "polished_deepslate",
    "tuff", "polished_tuff", "calcite", "dripstone_block", "basalt", "smooth_basalt", "polished_basalt", "blackstone",
    "polished_blackstone", "gilded_blackstone", "netherrack", "obsidian", "crying_obsidian", "bedrock", "mud", "packed_mud",
    "bookshelf", "chiseled_bookshelf", "hay_block", "sponge", "wet_sponge", "ice", "packed_ice", "blue_ice", "snow_block",
    "chest", "trapped_chest", "barrel", "crafting_table", "furnace", "blast_furnace", "smoker", "smithing_table",
    "fletching_table", "cartography_table", "loom", "lectern", "enchanting_table", "tnt", "pumpkin", "carved_pumpkin",
    "jack_o_lantern", "melon", "glowstone", "sea_lantern", "shroomlight", "ender_chest", "smooth_stone", "smooth_quartz",
    "smooth_sandstone", "quartz_pillar", "moss_block", "mud_bricks", "resin_block", "resin_bricks", "sandstone",
    "red_sandstone", "quartz_block", "chiseled_quartz_block", "prismarine", "dark_prismarine", "end_stone", "purpur_block",
    "oak_leaves", "spruce_leaves", "birch_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves", "cherry_leaves",
    "mangrove_leaves", "azalea_leaves", "pale_oak_leaves", "crimson_stem", "warped_stem",
}
# whole families, matched on the end of the name: planks, logs, bricks, concrete, wool, terracotta, ore, metal blocks
SOLID_SUFFIXES = ("_planks", "_log", "_wood", "_hyphae", "_bricks", "_concrete", "_wool", "_terracotta", "_ore",
                  "_block", "_stone", "_sandstone", "_nylium", "_stained_glass")
# shapes that are not full cubes; checked first so "oak_stairs" or "stone_brick_wall" is never solid by its suffix
THIN_SUFFIXES = ("_stairs", "_slab", "_fence", "_fence_gate", "_wall", "_pane", "_door", "_trapdoor", "_sign", "_wall_sign",
                 "_hanging_sign", "lantern", "torch", "_carpet", "_button", "_pressure_plate", "_flower", "_sapling", "rail",
                 "_bars", "_bed", "_banner", "_candle", "_head", "_skull", "_pot", "_roots", "_vine", "_stained_glass_pane")
THIN_NAMES = {"air", "cave_air", "void_air", "light", "short_grass", "tall_grass", "fern", "large_fern", "dead_bush", "vine",
              "snow", "iron_bars", "chain", "ladder", "water", "lava", "fire", "cobweb", "bamboo", "sea_pickle", "lily_pad",
              "glow_lichen", "scaffolding", "redstone_wire", "lever", "tripwire"}
# things that are not solid but still block head room (you cannot stand in a stair, slab or fence)
HEAD_BLOCKERS = ("_stairs", "_slab", "_fence", "_fence_gate", "_wall")

PATH_BLOCKS = ("gravel", "dirt_path", "cobblestone", "stone_bricks", "mossy_cobblestone", "polished_andesite", "packed_mud",
               "coarse_dirt")


def name(state):
    return (state or "minecraft:air").split("[")[0].replace("minecraft:", "")


def props(state):
    if not state or "[" not in state:
        return {}
    return dict(kv.split("=", 1) for kv in state.split("[", 1)[1].rstrip("]").split(",") if "=" in kv)


def is_solid(state):
    """True for a full block you cannot stand inside."""
    n = name(state)
    if not state or n in THIN_NAMES or n.endswith(THIN_SUFFIXES):
        return False
    return n in SOLID_NAMES or n.endswith(SOLID_SUFFIXES)


def is_step(state):
    return name(state).endswith(("_stairs", "_slab"))


def blocks_head(state):
    return is_solid(state) or name(state).endswith(HEAD_BLOCKERS)


def shape(state):
    """'full', 'bottom_stair', 'top_stair', 'bottom_slab', 'top_slab' or None (not something you stand on)."""
    n, p = name(state), props(state)
    if n.endswith("_stairs"):
        return "bottom_stair" if p.get("half", "bottom") == "bottom" else "top_stair"
    if n.endswith("_slab"):
        return {"bottom": "bottom_slab", "top": "top_slab", "double": "full"}.get(p.get("type", "bottom"), "bottom_slab")
    return "full" if is_solid(state) else None


def feet(state, y):
    """Standing height on top of this block."""
    return y + (0.5 if shape(state) in ("bottom_stair", "bottom_slab") else 1.0)


def feet_dir(state, y, dv, end):
    """Feet height on a block walked in direction dv: a bottom stair is low on its front side, high on its back."""
    if shape(state) == "bottom_stair":
        f = DV.get(props(state).get("facing"))
        if f == dv:
            return y + (0.5 if end == "in" else 1.0)
        if f == (-dv[0], -dv[1]):
            return y + (1.0 if end == "in" else 0.5)
        return y + 0.5
    return feet(state, y)


def _fmt(p):
    return f"({p[0]}, {p[1]}, {p[2]})"


def _label(state):
    n = name(state)
    return "Stair" if n.endswith("_stairs") else "Slab" if n.endswith("_slab") else "Path block"


def _floating(C):
    out = []
    ground = min(p[1] for p in C)
    seen = set()
    for p in sorted(C, key=lambda q: (q[1], q[0], q[2])):
        if p in seen:
            continue
        comp = [p]
        seen.add(p)
        k, grounded = 0, False
        while k < len(comp):
            x, y, z = comp[k]
            k += 1
            grounded = grounded or y == ground
            for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (x + a, y + b, z + c)
                if q in C and q not in seen:
                    seen.add(q)
                    comp.append(q)
        if not grounded:
            at = min(comp, key=lambda q: (q[1], q[0], q[2]))
            out.append(("floating", at, f"A group of {len(comp)} block{'s' if len(comp) != 1 else ''} near {_fmt(at)} "
                                        f"is not connected to the ground, so it floats"))
    return out


def _floating_on_land(C, ground):
    """Floating parts of what was BUILT on terrain: groups of new blocks that touch no untouched ground block.
    The terrain itself (tree leaves, overhangs) is not checked."""
    out = []
    new = {p for p, s in C.items() if not ground.untouched(C, p)}
    seen = set()
    for p in sorted(new, key=lambda q: (q[1], q[0], q[2])):
        if p in seen:
            continue
        comp = [p]
        seen.add(p)
        k, grounded = 0, False
        while k < len(comp):
            x, y, z = comp[k]
            k += 1
            for a, b, c in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                q = (x + a, y + b, z + c)
                if q in new:
                    if q not in seen:
                        seen.add(q)
                        comp.append(q)
                elif ground.is_land(C, q):
                    grounded = True
        if not grounded:
            at = min(comp, key=lambda q: (q[1], q[0], q[2]))
            top = ground.top.get((at[0], at[2]))
            gap = f", {at[1] - top - 1} block{'s' if at[1] - top - 1 != 1 else ''} above the ground" if top is not None and at[1] > top + 1 else ""
            out.append(("floating", at, f"A group of {len(comp)} block{'s' if len(comp) != 1 else ''} near {_fmt(at)} "
                                        f"is not connected to the ground, so it floats{gap}"))
    return out


def _free(C, p):
    """Nothing there at all (air, or no block)."""
    return name(C.get(p)) in ("air", "cave_air", "void_air")


def _walkable_like(C, x, y, z):
    s = C.get((x, y, z))
    return shape(s) in ("bottom_stair", "bottom_slab") or name(s) in PATH_BLOCKS


def _is_ground_path(C, x, y, z):
    """A path-material block is path only when it sits on something solid, is the highest block of its column within
    3 blocks (nothing above: not a wall or roof top), and a neighbour at the same height or one up or down is walkable too."""
    if not is_solid(C.get((x, y - 1, z))):
        return False
    if not all(_free(C, (x, y + h, z)) for h in (1, 2, 3)):
        return False
    return any(_walkable_like(C, x + a, y + dy, z + c) for a, c in DV.values() for dy in (-1, 0, 1))


def _is_roof_step(C, x, y, z):
    """The single ridge stair of an odd-width gable roof: stairs one block lower on both opposite sides of it (a roof
    peak). A climb on a road never has lower stairs on both sides of one stair."""
    def low(a, c):
        return name(C.get((x + a, y - 1, z + c))).endswith("_stairs")
    return (low(1, 0) and low(-1, 0)) or (low(0, 1) and low(0, -1))


class _Stand:
    """Standing spots (x, z, y): a stair/slab/solid block with nothing solid or stepped directly above. Worked out on demand."""

    def __init__(self, C):
        self.C = C
        self.memo = {}

    def __contains__(self, key):
        r = self.memo.get(key)
        if r is None:
            x, z, y = key
            g = self.C.get
            s = g((x, y, z))
            r = bool((is_solid(s) or is_step(s)) and not is_solid(g((x, y + 1, z))) and not is_solid(g((x, y + 2, z)))
                     and not is_step(g((x, y + 1, z))))
            self.memo[key] = r
        return r


def _terrain_burials(C, ground, cells):
    """Path blocks the build put into the land that are covered by untouched ground (a path that runs into a hill)."""
    out = []
    for (x, y, z), s in cells:
        if name(s) not in PATH_BLOCKS:
            continue
        cover = next((h for h in (1, 2) if ground.is_land(C, (x, y + h, z)) and C.get((x, y + h, z)) is not None), None)
        if cover is None:
            continue
        if any(name(C.get((x + a, y + dy, z + c))) in PATH_BLOCKS or shape(C.get((x + a, y + dy, z + c))) in ("bottom_stair", "bottom_slab")
               for a, c in DV.values() for dy in (-1, 0, 1)):
            out.append(("buried_path", (x, y, z),
                        f"Path block at {_fmt((x, y, z))} runs into the terrain: the ground is {cover} above it, "
                        f"so cut the hill away or move the path up"))
    return out


def run(blocks, size=None, ground=None):
    """All findings for a build, capped per check. `size` is accepted for callers that have it; no check needs it yet.
    `ground` (terrain.Ground) = the build sits on terrain: floating is measured against the land, and paths that run into
    the land are buried paths. The terrain's own blocks are never reported."""
    C = blocks
    if not C:
        return []
    g = C.get
    found = list(_floating_on_land(C, ground)) if ground is not None else list(_floating(C))
    stand = _Stand(C)

    walk = {}
    cells = C.items() if ground is None else [(p, s) for p, s in C.items() if not ground.untouched(C, p)]
    if ground is not None:
        found += _terrain_burials(C, ground, cells)
    for (x, y, z), s in cells:
        n, sh = name(s), shape(s)
        if sh not in ("bottom_stair", "bottom_slab") and n not in PATH_BLOCKS:
            continue
        if n in PATH_BLOCKS and not _is_ground_path(C, x, y, z):
            continue                                              # wall and roof tops are not paths
        if sh in ("bottom_stair", "bottom_slab") and _is_roof_step(C, x, y, z):
            continue                                              # the ridge stair of a roof is not a path
        walk[(x, y, z)] = s
        here = (x, y, z)
        for h in (1, 2):
            if is_solid(g((x, y + h, z))):
                found.append(("buried_path", here,
                              f"{_label(s)} at {_fmt(here)} has a solid block {h} above it, so nobody can walk on it"))
                break
        else:
            for h in (1, 2):                                      # not solid, but a stair/slab/fence still takes the room
                if blocks_head(g((x, y + h, z))):
                    found.append(("headroom", here,
                                  f"{_label(s)} at {_fmt(here)} has a {name(g((x, y + h, z)))} {h} above it, so there are "
                                  f"not 2 free blocks of headroom"))
                    break

    pairs = set()
    for (x, y, z), s in walk.items():
        if (x, z, y) not in stand:
            continue
        for a, c in DV.values():
            for dy in (-1, 0, 1):
                q = (x + a, y + dy, z + c)
                if (x + a, z + c, y + dy) in stand and q in walk:
                    key = tuple(sorted(((x, y, z), q)))
                    if key in pairs:
                        continue
                    pairs.add(key)
                    hb = feet_dir(g(q), y + dy, (a, c), "in")
                    ha = feet_dir(s, y, (a, c), "out")
                    if abs(hb - ha) > 0.6:
                        found.append(("jump_step", (x, y, z),
                                      f"Path at {_fmt((x, y, z))} to {_fmt(q)} is a {abs(hb - ha):g}-block jump, "
                                      f"so make the rise a bottom stair facing uphill"))
        if shape(s) == "bottom_stair":
            dv = DV.get(props(s).get("facing"))
            if not dv:
                continue
            up = (x + dv[0], z + dv[1], y + 1)
            upw = (x - dv[0], z - dv[1], y + 1)
            if upw in stand and up not in stand and (x - dv[0], y + 1, z - dv[1]) in walk:
                found.append(("wrong_facing", (x, y, z),
                              f"Stair at {_fmt((x, y, z))} faces {props(s).get('facing')} but the path climbs the other way, "
                              f"so its high side points downhill"))
            for side in ((dv[1], dv[0]), (-dv[1], -dv[0])):
                for dy in (0, 1):
                    p2 = (x + side[0], y + dy, z + side[1])
                    t = g(p2)
                    if name(t).endswith("_stairs") and p2 in walk and DV.get(props(t).get("facing")) in (side, (-side[0], -side[1])):
                        found.append(("corner_turn", (x, y, z),
                                      f"Stair at {_fmt((x, y, z))} is followed by a stair at {_fmt(p2)} that turns 90 degrees, "
                                      f"so put a flat landing at the turn"))

    for (x, y, z), s in cells:
        if name(s).endswith("_door") and props(s).get("half") == "lower":
            dv = DV.get(props(s).get("facing"))
            if dv:
                for sgn, word in ((1, "in front of"), (-1, "behind")):
                    p2 = (x + sgn * dv[0], y, z + sgn * dv[1])
                    if is_solid(g(p2)):
                        found.append(("door_blocked", (x, y, z),
                                      f"Door at {_fmt((x, y, z))} has a solid block {word} it at {_fmt(p2)}, so nobody can get through"))
                        break

    return _cap(found)


def _cap(found):
    """Keep the first CAP findings of each check; every kept finding carries the true count for its check."""
    count = collections.Counter(chk for chk, _, _ in found)
    shown = collections.Counter()
    out = []
    for chk, at, text in found:
        shown[chk] += 1
        if shown[chk] <= CAP:
            out.append({"check": chk, "at": list(at), "text": text, "count": count[chk]})
    return out


def counts(findings):
    """{check: true number of problems} (the list is capped, so use the stored count)."""
    by = {}
    for f in findings:
        by[f["check"]] = max(by.get(f["check"], 0), f.get("count", 1))
    return by


def total(findings):
    return sum(counts(findings).values())


def summary(findings):
    by = counts(findings)
    return f"{sum(by.values())} problems (" + ", ".join(f"{CHECK_LABELS.get(k, k)} {v}" for k, v in by.items()) + ")"
