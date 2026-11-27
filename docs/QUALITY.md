# What makes a good building (BlockForge quality rules)

The owner's rule 145: BlockForge only gives good buildings and houses, at any size, never blocky ones. This page is the
rulebook behind `blockforge/quality.py`, the save gate and the `review` tool. The rules were read off seven reference
pictures the owner picked (wooden manors, farmhouses, a stilt manor and two layer-by-layer blueprints). The pictures
have an unknown licence: nothing from them is copied or shipped, only the rules below.

## The score

`quality.score(blocks, size=None, prompt=None)` gives every building twelve parts, each 0-100, and a weighted total.
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

| Part | Weight | Good (from the references) | Penalised |
| --- | --- | --- | --- |
| Wall contrast | 16 | On the render (`_view`): the fill (CIE lightness 45+: oak 57, birch 72, stripped birch/oak, white terracotta 75) against the log frame (oak log 38, spruce or dark oak log 18-20), 20+ apart; 60%+ of the seen wall light | One wood tone everywhere; walls mostly dark (spruce planks 38, dark oak) |
| Looks (colours) | 14 | On the render: mean wall lightness 50+ (40%), a coloured roof - teal, green, warm wood (25%), the colour histogram close to the nearest reference photo, 0.60+ (35%) | Near-black walls (mean lightness 35 or less), a deepslate or grey roof, a colour mix unlike the references; plus the dark cap on the total |
| Storeys | 14 | 2 floors (0.8) or 3+ (1.0), each a level with walls round it and a flat ceiling (an attic under the roof slopes is not a storey); height to the top of the walls / length of the top storey 0.45+ | One floor on a house that is not small; long and low (0.2 or less gets nothing for the height). Small houses (size or prompt says tiny, small, little, hut, cottage, cabin or shed, or 36 room columns or fewer) may have one floor |
| Windows | 11 | Glass on 15%+ of every facade (a missing side counts as blank), framed (shutters, sill, box), big: 4+ panes together (2 x 2) | A few 1 x 2 windows; blank sides |
| Balconies | 10 | Outdoor floors 3+ blocks above the ground with a fence railing: one (35), a second (25), 24+ cells in all (25), an outside stair of 4+ steps (landings allowed) climbing to one (15) | None |
| Roof colour and layers | 10 | The main roof a colour of its own (60): far from the wall colours (RGB distance 50+) and another hue (60 degrees apart, or grey against coloured) - teal, green, red - and colourful on the render (a near-black or grey roof keeps only 30% of these points unless a dark build was asked); roof planes (bottom stairs open to the sky) at 3+ heights 2+ apart (40): storey bands, wing and porch roofs, the main roof | A roof in the wall wood (spruce on spruce); one roof height |
| Facade depth | 5 | Log posts and beams stick out 1 block from the wall plane on 10%+ of the wall surface; a frame in a different wood than the infill | Flat wall runs longer than 5 blocks with no post, window or step; shutters and boxes alone count less than real posts |
| Roof | 5 | Pitched stair/slab roof, eaves overhang the walls on 60%+ of the outline (2 blocks over a framed wall), trim (barge boards, eave row, ridge) in a second material | Flat box top (0 for the pitch); one roof plane over 140 blocks with no cross gable or dormer (up to -25) |
| Massing | 4 | A main volume plus a wing, porch, balcony or annex; 2-3 different ridge heights; an L or T plan | A single box with one roof height |
| Palette | 3 | 3-6 main materials with roles: logs for the frame, one wall fill, a different roof, 4+ accents (glass, trapdoors, lanterns, fences, pots) | One material; the roof in the wall material; 9+ main materials (random) |
| Detail | 4 | A glass pane per 4 metres of wall or more, windows framed (shutters, flower box, sill), 5+ kinds of outside detail, a chimney 2+ above the roof | Bare walls, no chimney |
| Surroundings | 4 | A path of 4+ cells to the door; fence, plants, farm, water, outdoor light, paving around the house | A house standing on nothing |

The save gate is `QUALITY_MIN = 60`. The size hint and the prompt only decide "small" (one storey is then fine);
`mcp_server` passes the session title, `engine` the prompt, `bench/score.py` the prompt in meta.json.

Calibration (tests/test_quality.py; tests/data holds the three bench builds):

| Build | Round 1 | Round 2 | Round 3 (looks on the render) |
| --- | --- | --- | --- |
| Plain 9 x 9 cobblestone box, flat roof | 8 | 3 | 7 |
| Plain house shell with a gable roof | 40 | 45 | 54 |
| Bench 1.16 wooden manor (long, low, dark spruce frame, spruce roof) | 87 | 58 | 35 |
| Bench 1.16 small cottage (one storey, dark logs, dark oak roof; prompt "A small cottage.") | 94 | 52 | 41 |
| 1.13.0 wooden manor (dark oak frame, spruce and birch, deepslate roof: "reads near-black") | - | 85 | 52 (capped; 94 if the prompt had asked for a dark/gothic manor) |
| `light_manor` rebuilt in spruce, dark oak and deepslate (same shape) | - | - | 39 (94 with "a spooky manor") |
| Pattern cottage (2 storeys, birch in oak logs, green roof with oak trim) | 97 | 85 | 90 |
| Pattern manor (plaster in oak logs, teal roof with oak trim) | 98 | 86 | 92 |
| Pattern village, as a town (light fills, teal/red/brick/green/spruce roofs) | 98 | 87 | 89 |
| Reference-like manor `light_manor` (3 storeys, birch in oak logs, teal layered roof with oak trim, storey bands, balconies, terrace garden, outside stair) | - | 94 | 95 |

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

**Windows and detail.** Big 2 x 2 panes in every bay of every floor (12-20% of each facade is glass), white-framed:
a stripped birch lintel over, birch trapdoor shutters on both sides, a flower box directly under the panes (grass block
with one kind of flower, trapdoors round its front, sides and bottom). Flowers only in those boxes and in the garden,
never scattered over the walls (on the render they read as coloured noise). Lanterns by the door and on posts, a
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
  `farm_plot`, `fence_garden`, `site`, `road`, `plaza`. Each passes `checks.run` with no path, door or floating
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
