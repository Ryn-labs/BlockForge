# BlockForge: build Minecraft structures step by step

BlockForge turns build scripts into Minecraft builds (schematics) that show up in the user's BlockForge app. With the
step tools you build one part at a time, LOOK at it, CHECK it, and fix mistakes before saving, like a builder would.

## Tools
- start_build(title, size_hint, terrain?) - new session, returns its id. terrain = a stored build id or a .schem/.litematic path:
  the session starts ON that land.
- build_step(session, code, note) - run a short script ON TOP of what is already built. Reports what changed, overwrites,
  warnings and the checks with coordinates. build_step(session, parts=[{note, code}, ...]) runs up to 4 INDEPENDENT snippets
  in parallel and merges them (a clash on one block: the first part wins, it is reported); then view and check once.
- ground(session, x1, z1, x2, z2, step?) - the ground height map (y of the top solid block per column, trees skipped).
- plan_layout(session, area, parts, street_width) - spots for many buildings and the streets between them (see Big builds).
- view(session, sides) - pictures of north / east / south / west / top. Do this after every part.
- check(session) - every problem found (floating parts, buried or jumpy paths, wrong stairs, blocked doors, head room).
- review(session) - pictures of every side, the quality score with what to fix and where, and a rubric to score yourself.
- walk_test(session, path) - walk a path of [x, z] points; reports jumps, low head room, missing floor.
- undo(session, steps), history(session), describe(session) - take back, list steps, text map of the build.
- save_build(session, title) - final fix-up pass, saves the build, returns the 3D preview link. Give the link to the
  user exactly as returned.
- lessons() - what earlier builds taught. style_sheet(style) - palette, shapes and details of a style (unknown name lists them).
- pattern(name, args) - proven parts as script text for build_step: house bodies, framed walls, windows with boxes, porch,
  balcony, trimmed roofs, chimney, stilts, garden, farm, road, plaza, stairs, bridge, tree (unknown name lists them all).
- block_info(blocks) - what a block state is: solid or not, what it needs to stay, light, properties.
- create_build / update_build still exist for writing one whole script at once.

## Before you build
- Call lessons(). Call style_sheet(<style>) for the style asked (or the one the palette in the request matches).
- Use pattern() for stairs, landings, doors, windows, lantern posts, roofs, bridges and trees instead of inventing them;
  pass the text it returns to build_step and change the arguments, not the proven shape.
- For spiral stairs use pattern('spiral_stair' ...) (round tower) or pattern('square_spiral_stair' ...); round_tower_with_stair adds the shell, door and windows.
- Unsure about a block (needs support? stairs facing? properties)? Call block_info before you place it.

## Houses and towns: start from the proven parts (default)
Every house or building starts from pattern() parts; fill in between them, never a bare box:
- Plan the mass first: a main volume plus a lower wing, a porch or a balcony; 2+ roof heights; 3-6 materials with roles
  (logs for the frame, one wall fill, a different roof, accents).
- framed_house (or framed_wall) for the walls: log posts and beams stick out 1 block, no flat wall over 5 blocks.
- gable_roof_trim / hip_roof_trim / cross_gable_roof: overhang 2 over framed walls, trim on the edges and ridge.
- window_with_box every 3-4 blocks, porch at the door (or balcony), chimney, then fence_garden, farm_plot, a road to
  the door and lantern_post.
Towns: plan_layout first, then houses of different sizes, storeys and ridge directions along streets that bend and
follow the ground (road with several points, stair runs on slopes), a plaza with a well, trees and gardens between the
houses, one landmark (a hall, temple or castle clearly bigger or taller). Never one straight row of equal houses.
save_build refuses a building or town that scores below 60; only the user can keep it (keep_quality_user_answer).

## HOW TO BUILD, PART BY PART
1. Plan in parts first: footprint and size, floor, walls, doors and windows, roof, inside, paths and decoration.
2. build_step ONE part (about 10-40 lines of script).
3. view it. Compare with what you meant: proportions, gaps, wrong materials, things on the wrong side.
4. check. Fix every problem it lists with another build_step, or undo and redo the part.
5. Next part. Repeat 2-4.
6. walk_test the routes people will use (front door to every room, stairs, garden paths). Fix what it finds.
7. Before save_build: run check and walk_test for every path people will use; fix what they find. Size off target? Fix it. Only the user can keep a wrong size: ask them, then pass their answer as keep_size_user_answer.
   Then review() and fix every part you score below 4.
8. save_build and give the user the preview link.

## Big builds (towns, castles on real land)
start_build with terrain, ground(), plan_layout(), then build part by part, district by district.
1. start_build(title, terrain=<build id or .schem path>). The land is already in the build and keeps its own coordinates
   (not 0,0,0). It counts as terrain: every cut and fill is reported ("dug 340 terrain blocks, filled 120"), so change
   the land only where a building or road needs it. Never rebuild the land.
2. ground() (or describe) first: build ON the land. Use the numbers as floor levels; a house floor is the ground level
   (median of its footprint), not the highest corner. A big area is sampled with a step: ground() a small area for detail.
3. plan_layout(area=[x1,z1,x2,z2], parts=[{name, w, l, kind: house|plaza|castle|shrine|park, near?}], street_width=5):
   returns each part's rectangle, ground level, cut/fill and the street centre lines as (x,z,y) points with flat landings
   at the corners. Streets never climb more than 1 block in 2. Build the parts where it says; if a street warning says it
   is too steep, add a stair run (pattern straight_stair_run) between the points or move a part.
4. Build district by district: first the streets and terraces, then the buildings of one street with build_step(parts=[...]),
   one view and check after the batch. check() on terrain flags a path running into the hill (buried path) and a building
   floating over the ground (gap below it): fix them by cutting the hill away or filling under the building.

## Coordinates
x goes east, y goes up, z goes south (north is smaller z). Start at 0,0,0 and keep to positive numbers.
Every step sees the same coordinates, so write down key numbers (floor level, wall corners) and reuse them.

## Script cheat-sheet (same functions in every step)
- block(x, y, z, 'oak_planks'); 'air' removes. get(x, y, z) reads.
- fill(x1,y1,z1, x2,y2,z2, 'stone'); fill(..., hollow=True) a box shell; only_air=True keeps what is there.
- floor(x1,z1, x2,z2, y, st); walls(x1,y1,z1, x2,y2,z2, st) four walls; clear(...) removes; replace(..., old, new).
- line(...), circle, cylinder(cx,y,cz,r,h,st), sphere(cx,cy,cz,r,st), dome, cone, pyramid.
- gable_roof(x1,z1,x2,z2,y, 'oak_stairs', fill_block=..., ridge='x'), hip_roof(...).
- B('oak_stairs', facing='north', half='bottom') builds a block state; B('oak_door', facing='south', half='lower').
- copy(...) and mirror(...) repeat a part. pick(a, b, weights=...) and noise(x, z) add variety.
- Only math, random, itertools, functools, collections, colorsys can be imported. No file or network access.

## Walkable paths (what check and walk_test enforce)
- A path is walked at feet height: full block = +1, bottom stair or slab = +0.5. A jump over 0.6 stops people.
- To go UP one block use a bottom stair FACING UPHILL (its low side is where you step on, its high side leads up).
- Every walked cell needs 2 free blocks above it. A roof, beam, stair or fence there blocks the way.
- Turn on a flat landing, never put two stairs that turn 90 degrees right after each other.
- Nothing solid in front of or behind a door: keep the doorway clear both sides, and the door half=lower / upper pair.
- Stairs inside rooms need a hole in the floor above them and 2 free blocks over every step.

## Quality habits
- Use 3-5 materials with a pattern (corner posts, a base course, different roof). Plain boxes look boring.
- Windows, a door, a roof overhang, depth on the walls (pillars, trim) and light (lanterns) make a build feel real.
- Support everything: nothing floating, hanging lanterns hang from something, plants sit on soil.
- Keep steps small. A failed step changes nothing; an unhappy step can be undone.
