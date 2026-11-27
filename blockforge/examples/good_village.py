"""A good village made only from patterns: a two-storey hall with a layered roof as the landmark, four houses of
different sizes, storeys and roof directions (gable along x, gable along z, hip, a house with a wing), a paved plaza
with a well, winding dirt streets from every porch, trees, a garden, a farm and lantern posts. Quality >= 70 as a
town (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Good village (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground floor walls start here; the grass is at y 1
W = dict(shutter="spruce_trapdoor", box="spruce_trapdoor", lintel="stripped_spruce_log")


def _windows(spots):
    return [P.window_with_box(x, y, z, facing, flower=("poppy", "cornflower", "dandelion", "allium")[i % 4], **W)
            for i, (x, y, z, facing) in enumerate(spots)]


def code():
    parts = [P.site(-26, -6, 48, 46, Y - 1),
             # the hall: landmark, two floors, layered roof, porch to the plaza
             P.framed_house(0, 0, 18, 12, Y, floors=2, storey=4, spacing=6),
             *_windows([(x, y, z, f) for y in (Y + 1, Y + 6) for x, z, f in
                        ((3, 12, "south"), (15, 12, "south"), (3, 0, "north"), (9, 0, "north"), (15, 0, "north"),
                         (0, 3, "west"), (0, 9, "west"), (18, 3, "east"), (18, 9, "east"))]),
             P.cross_gable_roof(0, 0, 18, 12, Y + 10, "spruce_stairs", "dark_oak", "oak_planks", "south", 7, 2),
             P.porch(9, Y, 12, "south", 5, 3, path=0),
             # house A, west: ridge along z, door east
             P.framed_house(-20, 4, -12, 16, Y, fill="birch_planks", frame="dark_oak_log"),
             *_windows([(-20, Y + 1, 6, "west"), (-20, Y + 1, 14, "west"), (-18, Y + 1, 4, "north"),
                        (-14, Y + 1, 16, "south"), (-12, Y + 1, 6, "east"), (-12, Y + 1, 14, "east")]),
             P.gable_roof_trim(-20, 4, -12, 16, Y + 5, "dark_oak_stairs", "spruce", "z", 2, "birch_planks"),
             P.porch(-12, Y, 10, "east", 3, 3, wood="dark_oak", post="dark_oak_log", roof="dark_oak_stairs", path=0),
             # house B, east: ridge along x, door south
             P.framed_house(26, 6, 38, 14, Y),
             *_windows([(28, Y + 1, 14, "south"), (36, Y + 1, 14, "south"), (28, Y + 1, 6, "north"), (32, Y + 1, 6, "north"),
                        (36, Y + 1, 6, "north"), (38, Y + 1, 8, "east"), (38, Y + 1, 12, "east"), (26, Y + 1, 8, "west")]),
             P.gable_roof_trim(26, 6, 38, 14, Y + 5, "spruce_stairs", "dark_oak", "x", 2),
             P.chimney(39, Y - 1, 10, 14),
             P.porch(32, Y, 14, "south", 3, 3, path=0),
             # house C, south-west: small, one low floor, hip roof, door north
             P.framed_house(-18, 26, -10, 34, Y, storey=3, fill="white_terracotta", frame="oak_log"),
             *_windows([(-18, Y + 1, 28, "west"), (-18, Y + 1, 32, "west"), (-16, Y + 1, 34, "south"),
                        (-12, Y + 1, 34, "south"), (-10, Y + 1, 28, "east"), (-10, Y + 1, 32, "east")]),
             P.hip_roof_trim(-18, 26, -10, 34, Y + 4, "oak_stairs", "spruce", 2),
             P.porch(-12, Y, 26, "north", 3, 2, wood="oak", post="oak_log", roof="oak_stairs", path=0),
             # house D, south-east: ridge along z with a lower wing to the east, door west
             P.framed_house(24, 26, 32, 38, Y),
             P.framed_house(32, 28, 40, 36, Y, storey=3, skip=["west"], clear=True),
             *_windows([(26, Y + 1, 38, "south"), (30, Y + 1, 38, "south"), (26, Y + 1, 26, "north"),
                        (24, Y + 1, 28, "west"), (24, Y + 1, 36, "west"), (38, Y + 1, 36, "south"), (40, Y + 1, 30, "east")]),
             P.gable_roof_trim(34, 28, 40, 36, Y + 4, "spruce_stairs", "dark_oak", "x", 2, open_end="west"),
             P.gable_roof_trim(24, 26, 32, 38, Y + 5, "spruce_stairs", "dark_oak", "z", 2),
             P.porch(24, Y, 32, "west", 3, 3, path=0),
             # plaza, streets, green
             P.plaza(4, 18, 14, 26, Y - 1),
             P.road([[9, 16], [9, 18]], Y - 1),
             P.road([[4, 22], [-2, 22], [-6, 16], [-6, 10], [-8, 10]], Y - 1),
             P.road([[-6, 18], [-12, 22], [-12, 24]], Y - 1),
             P.road([[14, 22], [20, 22], [24, 19], [32, 19], [32, 18]], Y - 1),
             P.road([[20, 22], [19, 28], [19, 32], [20, 32]], Y - 1),
             P.lantern_post(2, Y, 17, "medieval"),
             P.lantern_post(-4, Y, 24, "medieval"),
             P.lantern_post(22, Y, 25, "medieval"),
             P.tree("oak", -2, Y, 30, 6),
             P.tree("birch", 14, Y, 34, 7),
             P.tree("spruce", 44, Y, 22, 8),
             P.tree("oak", -24, Y, 22, 6),
             P.fence_garden(-20, 37, -8, 43, Y, gates=("north",)),
             P.farm_plot(42, Y, 2, 5, 7, "wheat")]
    return "".join(parts)
