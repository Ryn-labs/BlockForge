"""A manor in the look of the owner's reference houses, made only from patterns: a three-storey main house with a light
birch fill in a dark oak log frame, storey bands between the floors, a teal cross-gable roof with an oak trim, big 2 x 2
framed windows with shutters and flower boxes, a porch with a balcony over it, a back balcony on the top floor, a west
wing whose roof is a terrace garden reached by an outside stair with a landing, an east wing with its own teal roof, a
chimney, a front garden with a path, lantern posts, trees and farm plots behind. Quality >= 80 (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Light timber manor (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground floor walls start here; the grass is at y 1
S = 5                                   # storey: 5 free blocks, floor lines at Y+5 and Y+11
W = dict(shutter="birch_trapdoor", box="birch_trapdoor", lintel="stripped_birch_log", width=2, height=2)
FLOWERS = ("poppy", "cornflower", "dandelion", "allium", "azure_bluet", "red_tulip")


def _windows(spots):
    return [P.window_with_box(x, y, z, facing, flower=FLOWERS[i % len(FLOWERS)], **W)
            for i, (x, y, z, facing) in enumerate(spots)]


def _terrace():
    """The west wing's roof (planks at y Y+5, level with the main house's middle floor) as a terrace garden: a fence
    railing with a gap where the outside stair arrives, planters with flowers and bushes, lantern posts, and a door
    from the main house."""
    t = Y + S + 1
    out = ["# terrace garden on the west wing",
           f"fill(-13, {t}, 2, -13, {t}, 5, 'oak_fence')",            # west edge, open at z 6..7 for the stair
           f"fill(-13, {t}, 8, -13, {t}, 16, 'oak_fence')",
           f"fill(-12, {t}, 2, -2, {t}, 2, 'oak_fence')",             # north edge
           f"fill(-12, {t}, 16, -2, {t}, 16, 'oak_fence')",           # south edge
           f"fill(-11, {t}, 11, -8, {t}, 14, 'grass_block')",         # planters
           f"fill(-5, {t}, 11, -2, {t}, 14, 'grass_block')"]
    i = 0
    for x in (-11, -10, -9, -8, -5, -4, -3, -2):
        for z in (11, 12, 13, 14):
            if (x + z) % 3 == 0:
                out.append(f"block({x}, {t + 1}, {z}, B('oak_leaves', persistent=True))")
            else:
                out.append(f"block({x}, {t + 1}, {z}, {FLOWERS[i % len(FLOWERS)]!r})")
                i += 1
    for (x, z) in ((-13, 2), (-13, 16), (-2, 16)):                   # corner posts with lanterns
        out += [f"block({x}, {t}, {z}, B('dark_oak_log', axis='y'))", f"block({x}, {t + 1}, {z}, B('lantern', hanging=False))"]
    out += [f"block(0, {t}, 4, B('spruce_door', facing='west', half='lower', hinge='left', open=False))",
            f"block(0, {t + 1}, 4, B('spruce_door', facing='west', half='upper', hinge='left', open=False))"]
    return "\n".join(out) + "\n"


def code():
    floors = (Y + 1, Y + S + 2, Y + 2 * S + 3)                       # window sills of the three floors
    parts = [P.site(-24, -20, 48, 40, Y - 1),
             # main house 25 x 19, three floors of 5, posts every 6 (5-block bays round 2-wide windows)
             P.framed_house(0, 0, 24, 18, Y, floors=3, storey=S, style="light", spacing=6),
             # wings: west (its roof is the terrace), east (a teal gable roof), one floor each
             P.framed_house(-12, 3, 0, 15, Y, floors=1, storey=S, style="light", spacing=6, skip=["east"], clear=True),
             P.framed_house(24, 3, 36, 15, Y, floors=1, storey=4, style="light", spacing=6, skip=["west"], clear=True)]
    spots = []
    for fy in floors:
        for x in (2, 8, 14, 20):
            if not (fy == floors[1] and x == 14):                    # the front balcony door
                spots.append((x, fy, 18, "south"))
            if not (fy == floors[2] and x == 14):                    # the back balcony door
                spots.append((x, fy, 0, "north"))
    spots = [s for s in spots if not (s[1] == floors[0] and s[2] == 18 and s[0] == 14)]     # the porch
    spots += [(0, floors[1], 8, "west"), (0, floors[1], 14, "west"),
              (0, floors[2], 2, "west"), (0, floors[2], 8, "west"), (0, floors[2], 14, "west"),
              (24, floors[2], 2, "east"), (24, floors[2], 14, "east"),
              (-10, floors[0], 3, "north"), (-4, floors[0], 3, "north"), (-10, floors[0], 15, "south"),
              (-4, floors[0], 15, "south"),
              (26, floors[0], 3, "north"), (32, floors[0], 3, "north"), (26, floors[0], 15, "south"),
              (32, floors[0], 15, "south"), (36, floors[0], 5, "east"), (36, floors[0], 11, "east")]
    parts += _windows(spots)
    parts += [
        # storey bands between the floors (north and south), open where the porch, balconies and chimney are
        P.storey_band(0, 0, 24, 18, Y + S, "dark_oak_stairs", skip=["west", "east"], gaps=[[12, 19, 18, 22]]),
        P.storey_band(0, 0, 24, 18, Y + 2 * S + 1, "dark_oak_stairs", skip=["west", "east"],
                      gaps=[[12, -4, 18, -1], [21, -3, 21, -1]]),
        # roofs: the east wing's under the main eaves, then the main layered roof
        P.gable_roof_trim(24, 3, 36, 15, Y + 5, "teal", "oak", "x", overhang=2, fill="birch_planks", open_end="west"),
        P.cross_gable_roof(0, 0, 24, 18, Y + 3 * S + 3, "teal", "oak", "birch_planks", front="south", overhang=2),
        P.chimney(21, Y - 1, -2, height=31, block="bricks"),
        # front door with a porch, the balcony over it (door from the middle floor), the top floor's back balcony
        P.porch(15, Y, 18, "south", width=5, depth=3, wood="spruce", post="dark_oak_log", roof="dark_oak_stairs", path=3),
        P.balcony(13, Y + S, 19, "south", length=5, depth=2, wood="spruce", post="dark_oak_log", door=True),
        P.balcony(13, Y + 2 * S + 1, -1, "north", length=5, depth=3, wood="spruce", post="dark_oak_log", door=True),
        # the terrace garden on the west wing, reached by an outside stair with a landing
        _terrace(),
        P.external_stair(-15, Y, 15, "north", S + 1, width=2, flight=3, landing=2, block="spruce_stairs",
                         support="spruce_planks", rail="spruce_fence", rails="left"),
        # garden, lanterns, trees, farm plots behind
        P.lantern_post(12, Y, 24, "medieval"),
        P.lantern_post(18, Y, 24, "medieval"),
        P.fence_garden(-2, 27, 32, 37, Y, gates=("north",)),
        P.tree("oak", -12, Y, 26, 7),
        P.tree("birch", 40, Y, 26, 7),
        P.tree("oak", 42, Y, 2, 6),
        P.farm_plot(-10, Y, -17, 9, 7, "wheat"),
        P.farm_plot(6, Y, -17, 9, 7, "carrots"),
        P.farm_plot(26, Y, -17, 9, 7, "potatoes"),
    ]
    return "".join(parts)
