# What makes a good building (BlockForge quality rules)

The owner's rule 145: BlockForge only gives good buildings and houses, at any size, never blocky ones. This page is the
rulebook behind `blockforge/quality.py`, the save gate and the `review` tool. The rules were read off seven reference
pictures the owner picked (wooden manors, farmhouses, a stilt manor and two layer-by-layer blueprints). The pictures
have an unknown licence: nothing from them is copied or shipped, only the rules below.

## The score

`quality.score(blocks, size=None, prompt=None)` gives every building thirteen parts, each 0-100, and a weighted total.
Round 2 (27 Nov) added contrast, storeys, windows, balconies and roof style after the owner's reviewer found the score
too generous: two bench builds that look nothing like the references (long, low, all dark-brown wood) scored 87 and 94.
Round 3 (27 Nov, "looks") followed the owner's verdict on the 1.13.0 manor: it scored 85 but "the whole house reads
near-BLACK" (dark oak and deepslate everywhere, a black roof). The block lists said "a light fill in a dark frame";
the eye saw black. So the colours are now measured on the render, not on block lists:

- `quality._view` draws the four side views of the house with `render.nearest` (the block seen in each cell,
  coloured with render.py's block colour table - the same colours as the app's pictures), on the building's columns
  and 2 round them above the foundation, so sky, ground, garden and trees never count. Each cell is roof (stairs or
  slabs, the top of a column 3+ up), window (glass) or wall.
- Measured there: the mean CIE lightness of the walls, the share of wall cells that are light (45+), the frame
  (unstripped logs) against the fill lightness, the roof's colourfulness (chroma and lightness: near-black and grey
  roofs are 0) and a 64-bin colour histogram of the house (4 lightness bands x grey + 15 hue sectors, soft binning).
- `tools/ref_palette.py` (a dev tool, Pillow) made the histograms of the house areas of the seven reference pictures
  once; only those numbers are shipped (`blockforge/data/ref_palette.json`). The house is scored by its closeness
  (1 - total variation distance) to the nearest of the five photos; the two drawn plans (refs 6, 7) are stored but not
  scored against - their flat tiles, grid lines and paper are not what a house looks like.
- The dark cap: a house that reads dark scores at most 35 + 65 x brightness, where brightness = the smaller of
  (mean wall lightness - 35) / 15 and (light share - 0.15) / 0.4, each 0..1. A house with walls darker than about 41
  can not reach 60, whatever its shape. The finding says so ("reads dark ... the total is held at N").
- A dark look asked for is fine: `quality.dark_asked(prompt)` (dark, gothic, spooky, haunted, night, stronghold,
  fortress, blackstone, deepslate, witch, vampire ...; not "blacksmith") turns off the cap, the light-share part of
  the contrast, the looks part and the roof colourfulness. The prompt reaches the score from the engine, `bench/score.py`,
  the MCP session title and the chat/loop self-improvement.

Round 4 (28 Nov, "shape") followed the owner's next point: the 1.14-light manor had the right colours and scored 89,
but it is long, low and boxy with one long ridge, unlike reference houses 2 and 5 (a taller central block with a big
front gable, wings stepping down on both sides, varied roof heights, a grand front stair, balconies on the wings). The
shape is now measured on the render too (`quality._shape`, weight 20):

- `_silhouettes`: the outline of the house against the sky from each side, from `render.nearest` of the house cells
  (structural blocks on the building's columns and 2 round them; chimneys, lights, fences left out; 1-2 column spikes
  2+ over both neighbours - finials, posts - cut down). On each outline: the peaks (a top higher than both sides by
  2+, the ridge counted within 1 block of the top), the roof heights (peaks and flat runs of 3+ columns, 2+ apart) and
  the longest flat ridge.
- Silhouette variety (25%): 3 roof heights from each side, 3 gables on the entrance side and its back (1 on the
  others), no ridge longer than 13 blocks seen from any side (none of the points from 25); a flat top with no sloped
  peak anywhere keeps 40%.
- Height spread (20%): 3 roof heights over all sides and 5+ blocks from the lowest to the tallest.
- Longest straight wall (25%): the outline of the rooms seen from each side (`_wall_runs`; inner walls left out). A step
  of the wall line - a wing, a bay, a set-back - ends a run; log posts in the wall do not. 9 blocks or less is full,
  18 or more nothing (60%), and the share of the wall in runs over 9 (40%).
- Front feature (15%): on the entrance side (the side the lowest doors face) a gable end facing out (a sharp peak with
  the gable fill under it), a porch (posts and a roof 2-8 blocks out) and a stair or steps (3+ bottom stairs there).
- Hierarchy (15%): in the entrance view the tallest peak is in the middle (30-70% across, at most half the width),
  with a lower top (a gable or a flat wing ridge, 2+ lower) on the left and on the right, the two within 2 blocks of
  each other (symmetry with hierarchy).
- A small house (size or prompt small, or 100 room columns or fewer) is not asked for wings: its shape is 30%
  silhouette, 25% wall runs and 45% front feature (a gable or a porch over the door). But it still needs some
  massing (the reviewer, 28 Nov: the 1.14.0 chat cottage, a plain one-storey box with mostly brown walls, scored 75):
  a porch, lean-to or dormer, a chimney, 2 storeys or a loft (rooms under the roof over 30% of the plan), and a pale
  fill (birch, stripped birch, plaster: lightness 62+ on 30% of the seen wall; oak planks and logs do not count). With
  one of them missing the total is held at 59, each more 8 lower. A dark build asked for needs no pale fill.
- Wall runs bridge an inner wall that meets the outside wall (rooms side by side are one straight wall) and leave out
  the 2-high crawl space under a deck on stilts.
- The shape cap: a big house (not small, not a town) scores at most 30 + 70 x shape / 100, so one long box with one
  ridge can not pass the gate whatever its colours ("reads as one long box ... held at N").
- `patterns.manor_layout` builds the reference shape in one call (see below); `bay_window` and `dormer` break walls and
  roof planes.

| Part | Weight | Good (from the references) | Penalised |
| --- | --- | --- | --- |
| Wall contrast | 15 | On the render (`_view`): the fill (CIE lightness 45+: oak 57, birch 72, stripped birch/oak, white terracotta 75) against the log frame (oak log 38, spruce or dark oak log 18-20), 20+ apart; 60%+ of the seen wall light | One wood tone everywhere; walls mostly dark (spruce planks 38, dark oak) |
| Looks (colours) | 15 | On the render: mean wall lightness 50+ (40%), a coloured roof - teal, green, warm wood (25%), the colour histogram close to the nearest reference photo, 0.60+ (35%) | Near-black walls (mean lightness 35 or less), a deepslate or grey roof, a colour mix unlike the references; plus the dark cap on the total |
| Shape (massing and outline) | 20 | On the render: 3 roof heights and no ridge over 13 from every side, 3 gables on the entrance side, a central block taller than wings on both sides, no straight wall over 9 blocks, a front gable, porch and grand stair | One long box with one long ridge (capped at 30 + 70 x shape for a big house); long straight walls |
| Storeys | 10 | 2 floors (0.8) or 3+ (1.0), each a level with walls round it and a flat ceiling (an attic under the roof slopes is not a storey); height to the top of the walls / length of the top storey 0.45+ | One floor on a house that is not small; long and low (0.2 or less gets nothing for the height). Small houses (size or prompt says tiny, small, little, hut, cottage, cabin or shed, or 36 room columns or fewer) may have one floor |
| Windows | 10 | Glass on 15%+ of every facade (a missing side counts as blank), framed (shutters, sill, box), big: 4+ panes together (2 x 2) | A few 1 x 2 windows; blank sides |
| Balconies | 8 | Outdoor floors 3+ blocks above the ground with a fence railing: one (35), a second (25), 24+ cells in all (25), an outside stair of 4+ steps (landings allowed) climbing to one (15) | None |
| Roof colour and layers | 8 | The main roof a colour of its own (60): far from the wall colours (RGB distance 50+) and another hue (60 degrees apart, or grey against coloured) - teal, green, red - and colourful on the render (a near-black or grey roof keeps only 30% of these points unless a dark build was asked); roof planes (bottom stairs open to the sky) at 3+ heights 2+ apart (40): storey bands, wing and porch roofs, the main roof | A roof in the wall wood (spruce on spruce); one roof height |
| Facade depth | 4 | Log posts and beams stick out 1 block from the wall plane on 10%+ of the wall surface; a frame in a different wood than the infill | Flat wall runs longer than 5 blocks with no post, window or step; shutters and boxes alone count less than real posts |
| Roof | 3 | Pitched stair/slab roof, eaves overhang the walls on 60%+ of the outline (2 blocks over a framed wall), trim (barge boards, eave row, ridge) in a second material | Flat box top (0 for the pitch); one roof plane over 140 blocks with no cross gable or dormer (up to -25) |
| Massing | 2 | A main volume plus a wing, porch, balcony or annex; 2-3 different ridge heights; an L or T plan | A single box with one roof height |
| Palette | 2 | 3-6 main materials with roles: logs for the frame, one wall fill, a different roof, 4+ accents (glass, trapdoors, lanterns, fences, pots) | One material; the roof in the wall material; 9+ main materials (random) |
| Detail | 2 | A glass pane per 4 metres of wall or more, windows framed (shutters, flower box, sill), 5+ kinds of outside detail, a chimney 2+ above the roof | Bare walls, no chimney |
| Surroundings | 1 | A path of 4+ cells to the door; fence, plants, farm, water, outdoor light, paving around the house | A house standing on nothing |

The save gate is `QUALITY_MIN = 60`. The size hint and the prompt only decide "small" (one storey is then fine);
`mcp_server` passes the session title, `engine` the prompt, `bench/score.py` the prompt in meta.json.

Calibration (tests/test_quality.py; tests/data holds the three bench builds):

| Build | Round 1 | Round 2 | Round 3 (looks on the render) | Round 4 (shape) |
| --- | --- | --- | --- | --- |
| Plain 9 x 9 cobblestone box, flat roof | 8 | 3 | 7 | 14 |
| Plain house shell with a gable roof | 40 | 45 | 54 | 51 |
| Bench 1.16 wooden manor (long, low, dark spruce frame, spruce roof) | 87 | 58 | 35 | 35 |
| Bench 1.16 small cottage (one storey, dark logs, dark oak roof; prompt "A small cottage.") | 94 | 52 | 41 | 41 |
| 1.13.0 wooden manor (dark oak frame, spruce and birch, deepslate roof: "reads near-black") | - | 85 | 52 (capped; 94 if the prompt had asked for a dark/gothic manor) | 52 (66 with a dark prompt: held by its shape) |
| Bench 1.14-light manor (light birch in oak logs, teal roof, but one 41-block ridge, a 37-block straight wall) | - | - | 89 | 52 (shape 31, capped) |
| 1.14.0 chat cottage ("A small timber cottage with a garden.": one storey, no porch, no chimney, mostly oak logs and planks) | - | - | 75 | 43 (capped: 3 small-house needs missing) |
| `light_manor` rebuilt in spruce, dark oak and deepslate (same shape) | - | - | 39 (94 with "a spooky manor") | 42 (95 with "a spooky manor") |
| `manor_layout` alone on a plain site (central block, entrance bay, stepped wings, grand stair) | - | - | - | 95 (shape 97) |
| A one-storey small cottage, 9 x 7, gable and porch at the front (tests/test_quality.py `small_cottage`, "A small cottage.") | - | - | - | 84 (shape 100, no wings asked) |
| Pattern cottage (rebuilt round 4: 11 x 9, two storeys, front gable, porch, set-back wing, birch gables and boxes) | 97 | 85 | 90 | 92 |
| Pattern manor (rebuilt round 4: `manor_layout` facing east on stilts, plaster in oak logs, red roofs) | 98 | 86 | 92 | 90 |
| Pattern village, as a town (light fills, teal/red/brick/green/spruce roofs) | 98 | 87 | 89 | 88 |
| Reference-like manor `light_manor` (rebuilt round 4 on `manor_layout`, gardens, path, farm plots) | - | 94 | 95 | 96 |

The examples were rebuilt with the round 3 palette (the round 2 versions with dark oak frames and grey roofs would be
capped). The histogram on its own separates less than the brightness does: the light manor is 0.68 from its nearest
photo, the 1.13.0 manor 0.52, a cobblestone box 0.07 (flat block colours against shaded photos); the wall lightness
(57 against 39) and the roof colour (1.0 against 0.0) carry most of the difference.

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

Calibration: a straight row of five identical boxes scores 18 (round 1: 20); the pattern-built village 89 (round 1: 98).

## Rules per part, with numbers

**Walls (facade).** Timber frame: log posts every 4-6 blocks (a bay of 4-5 between posts holds one 2-wide window or a
door), a log beam on every floor line, posts and beams 1 block out of the infill, thick corners (a third post on the
diagonal). The infill is LIGHT - birch or oak planks, stripped birch or oak logs, plaster (white terracotta) - in an
oak or spruce log frame, never the same block as the frame; most of the wall seen from outside is the light fill (the
reference houses are light, warm wood all over). Dark oak, deepslate and blackstone walls only when the user asks for a
dark, gothic or spooky build. A stone or cobblestone foundation row under it. No flat stretch longer than 5 blocks.

**Storeys.** 2-3 storeys of 4-5 blocks, the walls about half as tall as the main volume is long; a storey band (a
skirt of stairs 2 out, at or 1 below each floor line) between them. A long low bar reads as a shed. A small hut or
cottage may keep one storey.

**Roof.** A colour of its own - teal (prismarine brick stairs, the default; warped stairs for a deeper teal), green
(oxidized copper), red, brick, or warm oak - with an oak trim; a near-black or grey roof (deepslate tiles) only when
asked; layers at 3+ heights (storey bands, wing and porch roofs, the main roof, a cross gable).
Stairs, 45 degrees, eaves 1 block past a plain wall and 2 past a framed wall, so the roof shades the posts.
Trim in a second wood (oak on teal): the eave row, the barge boards along both gable ends, the ridge cap. Gable triangles filled with the
wall fill. Over 15 blocks long: break the roof with a cross gable (its own gable end on the front) or dormers; lower wings
get their own roof below the main eaves. A soffit (upside-down stairs) under the overhang holds the eave.

**Massing.** A main volume of 2-3 storeys (storey 4-5 blocks), plus a lower wing, a porch with its own roof on posts,
balconies on posts or brackets with fence railings, a terrace (a wing roof as a terrace garden) reached by an outside
stair with landings. Two or three ridge heights.

**Shape (big houses).** Like references 2 and 5: a taller central block (3 storeys) with a big gable facing the front,
wings of 2 storeys stepping down on both sides (set back, their own lower gables), roofs at 3 heights and no ridge longer
than about 13 blocks, no straight wall over 9 blocks (step it with a wing, a bay window or a set-back), a grand front
stair with landings up to a porch, balconies on the wings, stilts or a stone terrace on uneven ground.
`patterns.manor_layout(x, y, z, facing)` builds all of it. A small cottage stays one block: short walls, a gable and
a porch at the front.

**Windows and detail.** Big 2 x 2 panes in every bay of every floor (12-20% of each facade is glass), white-framed:
a stripped birch lintel over, birch trapdoor shutters on both sides, a sill or a planter directly under the panes
(grass block with soft mixed plants - azure bluet, oxeye daisy, lily of the valley, fern, azalea - trapdoors in the
frame's wood round its front, sides and bottom). Planters under only some windows (every second one, ground and first
floor); the same strong flower under every window reads as a row of red squares from afar, and the looks part takes
points off for each such row of saturated same-colour patches on the side views (round 5). Flowers only in those
planters and in the garden, never scattered over the walls (on the render they read as coloured noise). Lanterns by the door and on posts, a
brick chimney 2+ blocks above the ridge, fences on porches and balconies.

**Surroundings.** A dirt or gravel path from the porch to a garden gate, a fenced garden with flowers and bushes, a
farm plot (farmland, a water channel, ripe crops, fence and gate), lantern posts, trees. On uneven ground or water:
stilts (posts down to the ground) under a deck.

## Where the rules live in code

- `blockforge/quality.py` - the score, findings with coordinates, fixes per part, the town score, the review rubric;
  `_view` measures the looks on `render.nearest`; `blockforge/data/ref_palette.json` (from `tools/ref_palette.py`)
  holds the reference histograms.
- `blockforge/patterns.py` - proven parts that follow these rules: `framed_house` / `framed_wall` (default
  `style='light'`: birch in oak logs; also `'oak'`, `'stripped'`, `'plaster'`, `'classic'`; `'dark'` only when asked), `window_with_box` (`width=2, height=2`), `porch`, `balcony`
  (`gap=` for a stair), `storey_band`, `external_stair`, `gable_roof_trim`, `hip_roof_trim`, `cross_gable_roof` (all
  three default to teal with an oak trim and take `stairs='green'`, `'red'`, `'brick'` ... from `ROOF_COLOURS`), `chimney`, `stilt_base`,
  `farm_plot`, `fence_garden`, `site`, `road`, `plaza`; `manor_layout` (the whole reference shape: central block,
  entrance bay, stepped wings, porch, grand stair, wing balconies, terrace or stilts; any facing), `bay_window`,
  `dormer`. Each passes `checks.run` with no path, door or floating
  problems; every stair pattern (`straight_stair_run`, `external_stair`, `switchback_landing`, `porch(steps=)`, balcony
  access, `storey_band`) has 0 jump steps and 0 corner turns by `checks.run` and by `bench/score.py`
  (tests/test_patterns.py). A jump step, corner turn or wrong facing finding now comes with a line naming those
  patterns (`checks.advice`, in `check`, `build_step` and the script-mode fix message). The bench manor's 24 jump steps
  and 40 corner turns were its own dormer roofs meeting the main slope, not its walking stairs.
- `blockforge/examples/` - a cottage, a manor, a village and `light_manor` (the reference look) built only from those
  parts.
- `mcp_server.save_build` refuses a building or town below 60 (the 3 weakest parts with fixes and coordinates);
  `accept_problems` does not cover it, only `keep_quality_user_answer` (the user's words), never in unattended mode.
- `engine.generate` (script mode) runs one quality fix round below 60 and keeps the new version only if it scores higher.
- `bench/score.py` reports a `quality` column.
