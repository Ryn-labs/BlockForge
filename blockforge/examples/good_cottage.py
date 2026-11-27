"""A good cottage made only from patterns: timber-framed main house, a lower wing (L plan), a trimmed gable roof with
2-block overhang, framed windows with shutters and flower boxes, a covered porch, a chimney, a fenced front garden with
a path, a farm plot and a lantern post. Quality >= 70 (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Good cottage (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground floor walls start here; the grass is at y 1


def code():
    w = dict(shutter="spruce_trapdoor", box="spruce_trapdoor", lintel="stripped_spruce_log")
    parts = [
        P.site(-6, -6, 28, 24, Y - 1),
        # main house 13 x 9 (bays of 3 between posts) and a lower wing to the east, 7 x 6
        P.framed_house(0, 0, 12, 8, Y, floors=1, storey=4, fill="oak_planks", frame="spruce_log"),
        P.framed_house(12, 0, 18, 5, Y, floors=1, storey=3, fill="oak_planks", frame="spruce_log", skip=["west"],
                       clear=True),
        # windows: front (south), back (north), west end, wing
        P.window_with_box(2, Y + 1, 8, "south", flower="poppy", **w),
        P.window_with_box(10, Y + 1, 8, "south", flower="cornflower", **w),
        P.window_with_box(2, Y + 1, 0, "north", flower="dandelion", **w),
        P.window_with_box(6, Y + 1, 0, "north", flower="allium", **w),
        P.window_with_box(10, Y + 1, 0, "north", flower="poppy", **w),
        P.window_with_box(0, Y + 1, 2, "west", flower="azure_bluet", **w),
        P.window_with_box(0, Y + 1, 6, "west", flower="poppy", **w),
        P.window_with_box(14, Y + 1, 5, "south", flower="dandelion", **w),
        P.window_with_box(14, Y + 1, 0, "north", flower="cornflower", **w),
        P.window_with_box(18, Y + 1, 2, "east", flower="allium", **w),
        # roofs: the wing tucks under the main roof's gable overhang
        P.gable_roof_trim(14, 0, 18, 5, Y + 4, "spruce_stairs", "dark_oak", "x", overhang=2, open_end="west"),
        P.gable_roof_trim(0, 0, 12, 8, Y + 5, "spruce_stairs", "dark_oak", "x", overhang=2),
        P.chimney(-1, Y - 1, 4, height=14, block="bricks"),
        # front door with a porch and a path to the garden gate
        P.porch(6, Y, 8, "south", width=3, depth=3, path=2),
        P.lantern_post(3, Y, 13, "medieval"),
        P.fence_garden(-4, 14, 16, 22, Y, gates=("north", "south")),
        P.tree("oak", 0, Y, 18, 6),
        P.farm_plot(19, Y, 9, 7, 7, "wheat"),
    ]
    return "".join(parts)
