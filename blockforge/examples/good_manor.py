"""A good manor made only from patterns, facing east and raised on log stilts (the way to build on uneven ground or
water): pattern manor_layout with a white plaster fill in an oak log frame and red roofs with an oak trim - a taller
three-storey central block with a big front gable, an entrance bay with its own lower gable, two stepped two-storey
wings with balconies, a porch and a grand stair with landings, framed windows with flower boxes, storey bands and a
chimney - then a path with lantern posts, a fenced front garden, trees and three farm plots behind.
Quality >= 80 (tests/test_quality.py)."""
from .. import patterns as P

TITLE = "Good manor (pattern example)"
SOURCE = "Made in this project from blockforge/patterns.py (no outside files)"
LICENCE = "Owned by the BlockForge project (same licence as the code)"

Y = 2                                   # ground level: the grass is at y 1


def code():
    parts = [P.site(-26, -30, 36, 30, Y - 1),
             P.manor_layout(0, Y, 0, "east", style="plaster", roof="red", raised=3, stilts=True, flower="cornflower"),
             # the stair foot is 17 east of the middle; a path on to the lane with lantern posts
             P.road([[18, 0], [34, 0]], Y - 1, width=3),
             P.lantern_post(20, Y, -3, "medieval"),
             P.lantern_post(20, Y, 3, "medieval"),
             P.fence_garden(14, -20, 30, -7, Y, gates=("south",), flowers=("cornflower", "allium", "azure_bluet")),
             P.fence_garden(14, 7, 30, 20, Y, gates=("north",), flowers=("cornflower", "allium", "azure_bluet")),
             P.tree("oak", 33, Y, -24, 7),
             P.tree("birch", 33, Y, 24, 7),
             P.farm_plot(-24, Y, -16, 7, 9, "wheat"),
             P.farm_plot(-24, Y, -4, 7, 9, "carrots"),
             P.farm_plot(-24, Y, 8, 7, 9, "potatoes")]
    return "".join(parts)
