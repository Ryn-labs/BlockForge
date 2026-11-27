# What makes a good building (BlockForge quality rules)

The owner's rule 145: BlockForge only gives good buildings and houses, at any size, never blocky ones. This page is the
rulebook behind `blockforge/quality.py`, the save gate and the `review` tool. The rules were read off seven reference
pictures the owner picked (wooden manors, farmhouses, a stilt manor and two layer-by-layer blueprints). The pictures
have an unknown licence: nothing from them is copied or shipped, only the rules below.

## The score

`quality.score(blocks)` gives every building six parts, each 0-100, and a weighted total:

| Part | Weight | Good (from the references) | Penalised |
| --- | --- | --- | --- |
| Facade depth | 20 | Log posts and beams stick out 1 block from the wall plane on 10%+ of the wall surface; a frame in a different wood than the infill | Flat wall runs longer than 5 blocks with no post, window or step; shutters and boxes alone count less than real posts |
| Roof | 20 | Pitched stair/slab roof, eaves overhang the walls on 60%+ of the outline (2 blocks over a framed wall), trim (barge boards, eave row, ridge) in a second material | Flat box top (0 for the pitch); one roof plane over 140 blocks with no cross gable or dormer (up to -25) |
| Massing | 15 | A main volume plus a wing, porch, balcony or annex; 2-3 different ridge heights; an L or T plan | A single box with one roof height |
| Palette | 15 | 3-6 main materials with roles: logs for the frame, one wall fill, a different roof, 4+ accents (glass, trapdoors, lanterns, fences, pots) | One material; the roof in the wall material; 9+ main materials (random) |
| Detail | 20 | A glass pane per 4 metres of wall or more, windows framed (shutters, flower box, sill), 5+ kinds of outside detail, a chimney 2+ above the roof | Bare walls, no chimney |
| Surroundings | 10 | A path of 4+ cells to the door; fence, plants, farm, water, outdoor light, paving around the house | A house standing on nothing |

The save gate is `QUALITY_MIN = 60`. Calibration (tests/test_quality.py): a plain 9 x 9 cobblestone box with a flat roof
scores 8; the old plain house shell with a gable roof 40; the pattern-built cottage 97, manor 98.

Not buildings: anything without a closed room (walls on four sides under a roof, 2 blocks of head room) - bridges,
trees, terrain, walls, open pavilions - gets no score and is never gated.

## Towns (3 or more buildings)

The total is half the house parts and half five town parts:

| Part | Weight | Good | Penalised |
| --- | --- | --- | --- |
| Streets | 25 | Streets reach every door (within 8 blocks); 40%+ of the street cells off the main straight corridor (bends, branches, following the contours) | No streets; one straight line |
| Variety | 25 | Footprints vary (spread 30%+), heights vary (15%+), a quarter of the houses turned with the ridge the other way | Identical houses |
| Open space | 20 | Between the houses: a plaza (5 x 5 paved), trees and plants, fences, farms, water, lantern posts | Nothing between the houses |
| Landmark | 15 | One building twice the median size or 5+ blocks taller (hall, temple, castle, manor) | All buildings alike |
| Density | 15 | Buildings cover 12-45% of the town area | Packed solid, or spread thin |

Calibration: a straight row of five identical boxes scores 20; the pattern-built village 98.

## Rules per part, with numbers

**Walls (facade).** Timber frame: log posts every 3-4 blocks (a bay of 3 between posts holds one window or door), a log
beam on every floor line, posts and beams 1 block out of the infill, thick corners (a third post on the diagonal). The
infill is planks, plaster (white terracotta) or birch, never the same block as the frame. A stone or cobblestone
foundation row under it. No flat stretch longer than 5 blocks.

**Roof.** Stairs, 45 degrees, eaves 1 block past a plain wall and 2 past a framed wall, so the roof shades the posts.
Trim in a darker wood: the eave row, the barge boards along both gable ends, the ridge cap. Gable triangles filled with the
wall fill. Over 15 blocks long: break the roof with a cross gable (its own gable end on the front) or dormers; lower wings
get their own roof below the main eaves. A soffit (upside-down stairs) under the overhang holds the eave.

**Massing.** A main volume of 1-2 storeys (storey 4-5 blocks), plus at least one of: a lower wing, a porch with its own
roof on posts, a balcony on posts or brackets, a terrace. Two or three ridge heights.

**Windows and detail.** 1 x 2 or 2 x 2 panes in each bay, a log lintel over, trapdoor shutters on both sides, a flower
box under (grass block with flowers, trapdoors round its front, sides and bottom). Lanterns by the door and on posts, a
brick chimney 2+ blocks above the ridge, fences on porches and balconies.

**Surroundings.** A dirt or gravel path from the porch to a garden gate, a fenced garden with flowers and bushes, a
farm plot (farmland, a water channel, ripe crops, fence and gate), lantern posts, trees. On uneven ground or water:
stilts (posts down to the ground) under a deck.

## Where the rules live in code

- `blockforge/quality.py` - the score, findings with coordinates, fixes per part, the town score, the review rubric.
- `blockforge/patterns.py` - proven parts that follow these rules: `framed_house`, `framed_wall`, `window_with_box`,
  `porch`, `balcony`, `gable_roof_trim`, `hip_roof_trim`, `cross_gable_roof`, `chimney`, `stilt_base`, `farm_plot`,
  `fence_garden`, `site`, `road`, `plaza`. Each passes `checks.run` with no path, door or floating problems.
- `blockforge/examples/` - a cottage, a manor and a village built only from those parts.
- `mcp_server.save_build` refuses a building or town below 60 (the 3 weakest parts with fixes and coordinates);
  `accept_problems` does not cover it, only `keep_quality_user_answer` (the user's words), never in unattended mode.
- `engine.generate` (script mode) runs one quality fix round below 60 and keeps the new version only if it scores higher.
- `bench/score.py` reports a `quality` column.
