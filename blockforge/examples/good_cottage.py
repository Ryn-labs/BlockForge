"""A good cottage made only from patterns: a compact two-storey timber-framed house (light birch fill in an oak log
frame, 11 x 9) whose green gable faces the front, a lower one-storey wing set back 2 (L plan, its own lower roof), a
storey band, 2 x 2 white-framed windows with birch shutters and a box of poppies under each, a covered porch under the
front gable with a balcony over it, a back balcony, a chimney, a fenced front garden with a path, a farm plot and a lantern post.
Small enough that it needs no wings: short walls, a gable and a porch at the front. Quality >= 80
(tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Good cottage (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground floor walls start here; the grass is at y 1


def _door(x, y, z, facing):
    """A door in the wall between a house and its wing (the wing has no outside door)."""
    return (f"block({x}, {y}, {z}, 'oak_door[facing={facing},half=lower,hinge=left,open=false]')\n"
            f"block({x}, {y + 1}, {z}, 'oak_door[facing={facing},half=upper,hinge=left,open=false]')\n")


def code():
    w = dict(width=2, height=2, box="birch_trapdoor")      # birch shutters, lintel and box (a pale wall), poppies
    w1 = dict(w, width=1)
    parts = [
        P.site(-8, -8, 28, 28, Y - 1),
        # main house 11 x 9, two floors (posts on the corners, beams on the floor lines); a wing to the east, 7 x 6
        P.framed_house(0, 0, 10, 8, Y, floors=2, storey=4, style="light", spacing=10),
        P.framed_house(10, 1, 16, 6, Y, floors=1, storey=3, style="light", spacing=6, skip=["west"], clear=True),
        _door(10, Y, 4, "east"),                            # the wing opens off the main house
        # windows: front (south) beside the porch, back (north), west end, wing
        P.window_with_box(2, Y + 1, 8, "south", **w1),
        P.window_with_box(8, Y + 1, 8, "south", **w1),
        P.window_with_box(2, Y + 6, 8, "south", **w1),
        P.window_with_box(8, Y + 6, 8, "south", **w1),
        P.window_with_box(2, Y + 1, 0, "north", **w),
        P.window_with_box(7, Y + 1, 0, "north", **w),
        P.window_with_box(0, Y + 1, 2, "west", **w),
        P.window_with_box(0, Y + 1, 5, "west", **w),
        P.window_with_box(0, Y + 6, 2, "west", **w),
        P.window_with_box(0, Y + 6, 5, "west", **w),
        P.window_with_box(12, Y + 1, 6, "south", **w),
        P.window_with_box(12, Y + 1, 1, "north", **w),
        P.window_with_box(16, Y + 1, 3, "east", **w),
        # a storey band between the floors, front and back (open at the porch and its balcony)
        P.storey_band(0, 0, 10, 8, Y + 4, skip=["west", "east"], gaps=[[3, 9, 7, 12], [2, -4, 8, -1]]),
        # roofs: the wing's lower roof tucks under the main roof's eaves; the main gable faces the front
        P.gable_roof_trim(10, 1, 16, 6, Y + 4, "green", "oak", "x", overhang=1, fill="birch_planks", open_end="west"),
        P.gable_roof_trim(0, 0, 10, 8, Y + 10, "green", "oak", "z", overhang=2, fill="birch_planks"),
        P.chimney(5, Y - 1, -1, height=20, block="bricks"),
        # front door with a porch under the gable and a balcony over it (door from the upper floor)
        P.porch(5, Y, 8, "south", width=3, depth=3, path=2),
        P.balcony(4, Y + 4, 9, "south", length=3, depth=2, door=True),
        P.balcony(3, Y + 4, -1, "north", length=5, depth=2, door=True),
        P.lantern_post(2, Y, 14, "medieval"),
        P.fence_garden(-6, 16, 16, 25, Y, gates=("north", "south")),
        P.tree("oak", -6, Y, 12, 6),
        P.farm_plot(19, Y, 10, 7, 7, "wheat"),
    ]
    return "".join(parts)
