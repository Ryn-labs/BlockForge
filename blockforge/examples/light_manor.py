"""A manor in the look and shape of the owner's reference houses (refs 2 and 5), made only from patterns with their
default palette: pattern manor_layout - a taller central block of three storeys (birch fill in an oak log frame) with a
big teal gable facing the front, a three-storey entrance bay with its own lower gable in front of it and a stair bay at
the back, two two-storey wings set back on both sides with their own lower front gables and a balcony each, a porch at
the door and a grand stair in two flights with landings up the stone terrace, 2 x 2 white-framed windows with flower
boxes, storey bands and a chimney. No straight wall is longer than 9 blocks. Round it: a path from the stair, lantern
posts, two flower gardens, trees and farm plots behind. Quality >= 85 (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Light timber manor (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground level: the grass is at y 1


def code():
    parts = [P.site(-30, -26, 30, 34, Y - 1),
             P.manor_layout(0, Y, 0, "south", raised=4),
             # a path from the foot of the grand stair (z 19) to the lane, lantern posts beside it
             P.road([[0, 20], [0, 33]], Y - 1, width=3),
             P.lantern_post(-3, Y, 22, "medieval"),
             P.lantern_post(3, Y, 22, "medieval"),
             P.lantern_post(-3, Y, 30, "medieval"),
             P.lantern_post(3, Y, 30, "medieval"),
             # flower gardens left and right of the path, in front of the wings
             P.fence_garden(-18, 14, -6, 25, Y, gates=("east",)),
             P.fence_garden(6, 14, 18, 25, Y, gates=("west",)),
             P.tree("oak", -24, Y, 12, 7),
             P.tree("birch", 24, Y, 12, 7),
             P.tree("oak", -24, Y, -14, 6),
             P.tree("birch", 25, Y, -16, 6),
             # farm plots behind the house
             P.farm_plot(-17, Y, -23, 9, 7, "wheat"),
             P.farm_plot(-4, Y, -23, 9, 7, "carrots"),
             P.farm_plot(9, Y, -23, 9, 7, "potatoes")]
    return "".join(parts)
