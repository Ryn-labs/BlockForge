"""A good manor made only from patterns: a two-storey timber-framed main house with a layered (cross gable) roof, two
lower wings with their own trimmed roofs and chimneys, a porch with a balcony over it, framed windows with shutters and
flower boxes on both floors, a big fenced front garden with trees and lantern posts, and two farm plots behind.
Quality >= 80 (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Good manor (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground floor walls start here; the grass is at y 1


def code():
    w = dict(shutter="spruce_trapdoor", box="spruce_trapdoor", lintel="stripped_spruce_log")
    flowers = ("poppy", "cornflower", "dandelion", "allium", "azure_bluet")
    parts = [P.site(-16, -17, 34, 30, Y - 1),
             # main house 19 x 13, two floors of 4, posts every 6; wings 13 x 7 on both sides, one floor
             P.framed_house(0, 0, 18, 12, Y, floors=2, storey=4, fill="oak_planks", frame="spruce_log", spacing=6,
                            flat=["west", "east"]),
             P.framed_house(-12, 3, 0, 9, Y, floors=1, storey=4, fill="oak_planks", frame="spruce_log", spacing=6,
                            skip=["east"], clear=True),
             P.framed_house(18, 3, 30, 9, Y, floors=1, storey=4, fill="oak_planks", frame="spruce_log", spacing=6,
                            skip=["west"], clear=True)]
    i = 0
    for floor_y in (Y + 1, Y + 6):                                   # main house, both floors
        for x in (3, 15):
            parts.append(P.window_with_box(x, floor_y, 12, "south", flower=flowers[i % 5], **w))
            i += 1
        for x in (3, 9, 15):
            parts.append(P.window_with_box(x, floor_y, 0, "north", flower=flowers[i % 5], **w))
            i += 1
    for x in (-9, -3, 21, 27):                                       # wings, front and back
        parts.append(P.window_with_box(x, Y + 1, 9, "south", flower=flowers[i % 5], **w))
        parts.append(P.window_with_box(x, Y + 1, 3, "north", flower=flowers[(i + 1) % 5], **w))
        i += 2
    parts += [P.window_with_box(-12, Y + 1, 6, "west", flower="poppy", **w),
              P.window_with_box(30, Y + 1, 6, "east", flower="poppy", **w),
              # roofs: wings first, then the main layered roof
              P.gable_roof_trim(-12, 3, 0, 9, Y + 5, "spruce_stairs", "dark_oak", "x", overhang=2, open_end="east"),
              P.gable_roof_trim(18, 3, 30, 9, Y + 5, "spruce_stairs", "dark_oak", "x", overhang=2, open_end="west"),
              P.cross_gable_roof(0, 0, 18, 12, Y + 10, "spruce_stairs", "dark_oak", "oak_planks", front="south", wing=7,
                                 overhang=2),
              P.chimney(-13, Y - 1, 4, height=13, block="bricks"),
              P.chimney(31, Y - 1, 8, height=13, block="bricks"),
              # porch at the front door with a balcony on top (door from the upper floor)
              P.porch(9, Y, 12, "south", width=5, depth=3, path=3),
              P.balcony(7, Y + 4, 13, "south", length=5, depth=3, ground_y=Y - 1, door=True),
              P.lantern_post(5, Y, 17, "medieval"),
              P.lantern_post(12, Y, 17, "medieval"),
              P.fence_garden(-14, 19, 32, 28, Y, gates=("north",)),
              P.tree("oak", -8, Y, 23, 7),
              P.tree("birch", 26, Y, 23, 7),
              P.farm_plot(-8, Y, -14, 9, 7, "wheat"),
              P.farm_plot(6, Y, -14, 9, 7, "carrots"),
              P.farm_plot(20, Y, -14, 9, 7, "potatoes")]
    return "".join(parts)
