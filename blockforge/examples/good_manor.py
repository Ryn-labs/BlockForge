"""A good manor made only from patterns: a two-storey timber-framed main house (white plaster fill in an oak log frame)
with a storey band and a teal layered (cross gable) roof with an oak trim, two lower wings with their own trimmed roofs and chimneys, a
porch with a balcony over it and a back balcony, 2 x 2 white-framed windows with a box of poppies under each on both floors, a
big fenced front garden with trees and lantern posts, and three farm plots behind. Quality >= 80 (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Good manor (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground floor walls start here; the grass is at y 1


def code():
    w = dict(width=2, height=2)                 # pattern defaults: birch shutters and lintel, oak box, poppies
    parts = [P.site(-16, -17, 34, 30, Y - 1),
             # main house 19 x 13, two floors of 4, posts every 6; wings 13 x 7 on both sides, one floor
             P.framed_house(0, 0, 18, 12, Y, floors=2, storey=4, style="plaster", spacing=6, flat=["west", "east"]),
             P.framed_house(-12, 3, 0, 9, Y, floors=1, storey=4, style="plaster", spacing=6, skip=["east"], clear=True),
             P.framed_house(18, 3, 30, 9, Y, floors=1, storey=4, style="plaster", spacing=6, skip=["west"], clear=True)]
    for floor_y in (Y + 1, Y + 6):                                   # main house, both floors
        for x in (2, 14):
            parts.append(P.window_with_box(x, floor_y, 12, "south", **w))
            parts.append(P.window_with_box(x, floor_y, 0, "north", **w))
    parts.append(P.window_with_box(8, Y + 1, 0, "north", **w))
    for x in (-10, -4, 20, 26):                                      # wings, front and back
        parts.append(P.window_with_box(x, Y + 1, 9, "south", **w))
        parts.append(P.window_with_box(x, Y + 1, 3, "north", **w))
    parts += [P.window_with_box(-12, Y + 1, 5, "west", **w),
              P.window_with_box(30, Y + 1, 5, "east", **w),
              # a storey band between the floors, front and back (open at the porch and the back balcony)
              P.storey_band(0, 0, 18, 12, Y + 3, skip=["west", "east"],
                            gaps=[[6, 13, 12, 16], [6, -4, 12, -1]]),
              # roofs: wings first, then the main layered roof
              P.gable_roof_trim(-12, 3, 0, 9, Y + 5, "teal", "oak", "x", overhang=2, open_end="east"),
              P.gable_roof_trim(18, 3, 30, 9, Y + 5, "teal", "oak", "x", overhang=2, open_end="west"),
              P.cross_gable_roof(0, 0, 18, 12, Y + 10, "teal", "oak", "white_terracotta", front="south", wing=7,
                                 overhang=2),
              P.chimney(-13, Y - 1, 4, height=13, block="bricks"),
              P.chimney(31, Y - 1, 8, height=13, block="bricks"),
              # porch at the front door with a balcony on top (door from the upper floor), a balcony at the back
              P.porch(9, Y, 12, "south", width=5, depth=3, path=3),
              P.balcony(7, Y + 4, 13, "south", length=5, depth=3, ground_y=Y - 1, door=True),
              P.balcony(7, Y + 4, -1, "north", length=5, depth=2, door=True),
              P.lantern_post(5, Y, 17, "medieval"),
              P.lantern_post(12, Y, 17, "medieval"),
              P.fence_garden(-14, 19, 32, 28, Y, gates=("north",)),
              P.tree("oak", -8, Y, 23, 7),
              P.tree("birch", 26, Y, 23, 7),
              P.farm_plot(-8, Y, -14, 9, 7, "wheat"),
              P.farm_plot(6, Y, -14, 9, 7, "carrots"),
              P.farm_plot(20, Y, -14, 9, 7, "potatoes")]
    return "".join(parts)
