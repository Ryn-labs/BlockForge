"""A good cottage made only from patterns: a two-storey timber-framed house (light birch fill in an oak log frame) with a
storey band, a lower wing (L plan), green gable roofs with an oak trim and 2-block overhang, 2 x 2 white-framed windows
with birch shutters and a box of poppies under each, a covered porch with a balcony over it, a side balcony, a chimney, a fenced front garden with a path,
a farm plot and a lantern post. Quality >= 70 (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Good cottage (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground floor walls start here; the grass is at y 1


def code():
    w = dict(width=2, height=2)                 # pattern defaults: birch shutters and lintel, oak box, poppies
    w1 = dict(w, width=1)
    parts = [
        P.site(-8, -6, 32, 28, Y - 1),
        # main house 16 x 11, two floors (posts every 5: 4-block bays) and a lower wing to the east, 9 x 7
        P.framed_house(0, 0, 15, 10, Y, floors=2, storey=4, style="light", spacing=5),
        P.framed_house(15, 2, 23, 8, Y, floors=1, storey=3, style="light", skip=["west"], clear=True),
        # windows: front (south), back (north), west end, wing
        P.window_with_box(2, Y + 1, 10, "south", **w),
        P.window_with_box(12, Y + 1, 10, "south", **w),
        P.window_with_box(2, Y + 6, 10, "south", **w),
        P.window_with_box(12, Y + 6, 10, "south", **w),
        P.window_with_box(2, Y + 1, 0, "north", **w),
        P.window_with_box(7, Y + 1, 0, "north", **w),
        P.window_with_box(12, Y + 1, 0, "north", **w),
        P.window_with_box(2, Y + 6, 0, "north", **w),
        P.window_with_box(7, Y + 6, 0, "north", **w),
        P.window_with_box(12, Y + 6, 0, "north", **w),
        P.window_with_box(0, Y + 1, 2, "west", **w),
        P.window_with_box(0, Y + 1, 7, "west", **w),
        P.window_with_box(0, Y + 6, 7, "west", **w),
        P.window_with_box(17, Y + 1, 8, "south", **w1),
        P.window_with_box(21, Y + 1, 8, "south", **w1),
        P.window_with_box(17, Y + 1, 2, "north", **w1),
        P.window_with_box(21, Y + 1, 2, "north", **w1),
        P.window_with_box(23, Y + 1, 4, "east", **w1),
        # a storey band between the floors, front and back (open at the porch)
        P.storey_band(0, 0, 15, 10, Y + 4, skip=["west", "east"], gaps=[[4, 11, 10, 13]]),
        # roofs: the wing tucks under the main roof's gable overhang
        P.gable_roof_trim(15, 2, 23, 8, Y + 4, "green", "oak", "x", overhang=2, open_end="west"),
        P.gable_roof_trim(0, 0, 15, 10, Y + 10, "green", "oak", "x", overhang=2),
        P.chimney(-2, Y - 1, 8, height=20, block="bricks"),
        # front door with a porch, a balcony over it and one on the west end (doors from the upper floor)
        P.porch(7, Y, 10, "south", width=3, depth=3, path=2),
        P.balcony(5, Y + 4, 11, "south", length=5, depth=2, door=True),
        P.balcony(-1, Y + 4, 1, "west", length=5, depth=2, ground_y=Y - 1, door=True),
        P.lantern_post(3, Y, 15, "medieval"),
        P.fence_garden(-4, 17, 18, 25, Y, gates=("north", "south")),
        P.tree("oak", -6, Y, 13, 6),
        P.farm_plot(21, Y, 12, 7, 7, "wheat"),
    ]
    return "".join(parts)
