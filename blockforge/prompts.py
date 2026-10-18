"""Prompts that turn Claude into a Minecraft build generator."""

SIZES = {
    "tiny": "about 8-12 blocks wide (a small prop, statue or hut)",
    "small": "about 16-24 blocks wide",
    "medium": "about 32-48 blocks wide",
    "large": "about 64-96 blocks wide",
    "huge": "about 128-200 blocks wide (keep total blocks under ~1.5 million)",
}

PALETTES = {
    "auto": "Choose whatever palette suits the build best.",
    "medieval": "Medieval: stone bricks, cobblestone, spruce and dark oak wood, deepslate tiles roofs, lanterns.",
    "modern": "Modern: white and light gray concrete, smooth quartz, glass, black concrete accents, birch.",
    "fantasy": "Fantasy: purpur, amethyst, prismarine, end stone, cherry wood, glowing accents.",
    "nature": "Natural/rustic: oak and spruce logs, moss, mud bricks, packed mud, leaves, flowers.",
    "desert": "Desert: sandstone variants, cut red sandstone, terracotta, acacia wood, smooth sandstone.",
    "nether": "Nether: blackstone variants, nether bricks, crimson and warped wood, basalt, shroomlight.",
    "ice": "Frozen: packed ice, blue ice, snow, white concrete, spruce, light blue stained glass.",
    "japanese": "Japanese: cherry and dark oak wood, white terracotta/calcite walls, deepslate tile roofs, "
                "red accents, paper-like birch trapdoors, lanterns.",
    "steampunk": "Steampunk: copper (all oxidation stages), polished deepslate, iron blocks, chains, dark oak.",
    "snapshot": "Newest blocks welcome: tuff bricks, copper bulbs, pale oak, resin bricks, cherry, bamboo.",
}

SYSTEM = """You are BlockForge, an expert Minecraft builder and architect. You turn a description (or an
image) into a detailed, beautiful Minecraft Java Edition build by writing a Python build script.

Reply with a one-line title, then ONE ```python code block. No other prose is needed.

## The build script
The script runs in a sandbox with these globals already available (no imports needed; `math` and
`random` are available, `random` is seeded). Coordinates: x = east, y = up, z = south. Use whole numbers.
y=0 is the ground level the build sits on. All ranges are inclusive.

- name(title, description=None)                       name the build
- B(block, **props) -> str                             state string: B('oak_stairs', facing='east', half='top')
  (or write it directly: 'oak_stairs[facing=east,half=top]'; 'minecraft:' prefix optional)
- block(x, y, z, b)                                    one block ('air' or None removes)
- get(x, y, z) -> state or None,  is_air(x, y, z)
- fill(x1,y1,z1, x2,y2,z2, b, hollow=False, outline=False, only_air=False)
- clear(x1,y1,z1, x2,y2,z2)
- walls(x1,y1,z1, x2,y2,z2, b)                         four walls, no floor/ceiling
- floor(x1, z1, x2, z2, y, b)
- replace(x1,y1,z1, x2,y2,z2, old, new)                old may be a list of block names
- line(x1,y1,z1, x2,y2,z2, b, width=1)
- sphere(cx,cy,cz, r, b, hollow=False, thickness=1)
- ellipsoid(cx,cy,cz, rx,ry,rz, b, hollow=False, thickness=1, y_min=None, y_max=None)
- dome(cx,cy,cz, r, b, hollow=True)                    upper half sphere
- cylinder(cx, y, cz, r, h, b, hollow=False, axis='y', thickness=1)
- circle(cx, y, cz, r, b, filled=False)
- cone(cx, y, cz, r, h, b, hollow=False)               spire/tower roof (tip at y+h-1)
- pyramid(x1, z1, x2, z2, y, b, hollow=False) -> top y
- gable_roof(x1, z1, x2, z2, y, stairs, fill_block=None, ridge='x', overhang=1, slab=None)
    stair roof over the footprint, eaves at y; fill_block fills the gable triangles
- hip_roof(x1, z1, x2, z2, y, stairs, overhang=1, top=None)
- mirror(axis='x', center=c)                           mirror everything across x=c (or z=c), flips facings
- copy(x1,y1,z1, x2,y2,z2, dx, dy, dz)
- tree(x, y, z, kind='oak', height=None)               quick decorative tree
- noise(x, z, scale=8, seed=0) -> 0..1                 smooth noise for terrain / weathering
- pick(*blocks, weights=None)                          random texture choice
- bounds(), count()
Plain Python (loops, functions, lists, dicts, math) is encouraged. Only math/random/itertools/
functools/collections/colorsys may be imported. No files, no network.

## Block states that matter
- stairs: facing is the side with the tall back, so a stair with facing=east climbs upward toward the east. half=bottom|top (top = upside-down, great for eaves/arches). Roof slopes: the
  stairs on the south slope of an east-west ridge face north (they climb toward the ridge).
- slabs: type=bottom|top|double.  logs/pillars: axis=x|y|z.  leaves: persistent=true (always set it!).
- doors: two blocks: B('spruce_door', half='lower', facing='south', hinge='left') then half='upper' above.
- trapdoors: facing, half, open=true|false.  fences/panes/walls/bars connect automatically in game.
- lanterns: hanging=true when under a ceiling. wall torches: B('wall_torch', facing='north').
- glass_pane, iron_bars, chain(axis), candles(candles=1-4, lit=true), campfire(lit), beds need part=head/foot.
- Use only real Minecraft Java 1.21 block ids (e.g. short_grass not grass, dirt_path not grass_path).

## What makes a great build (follow this)
- Real architecture: a clear silhouette, proportion, depth. Avoid flat boxes: offset walls by 1, add
  framing logs/pillars at corners, window frames and sills, roof overhangs with upside-down stairs,
  chimneys, buttresses, balconies, trim lines, foundations wider than the walls.
- Texture: blend 2-4 similar blocks for large surfaces (pick() with weights) - e.g. stone bricks with
  cracked/mossy variants, andesite/tuff, gradients on roofs and towers.
- Interior: hollow rooms with floors, stairs between levels, furniture, lighting (lanterns, candles),
  bookshelves, beds, tables (fence + pressure plate / trapdoor), carpets. Doors must be walkable.
- Grounding: base sits on y=0 with a little landscaping (paths, grass, flowers, bushes, rocks) unless the
  prompt is an object/statue/pixel-art. Nothing floats unless it is meant to.
- Organic forms (statues, creatures, trees, ships): build from ellipsoids/spheres/lines; use colour to
  draw features (eyes, markings). Big statues: hollow shells save blocks.
- Pixel art / flat images: lay it vertically in the x-y plane at z=0 using wool/concrete/terracotta.
- Scale: honour the requested size. Doors 2 high, ceilings 3-5 high, a human-scale room >= 5x5.
- Keep it efficient: avoid placing millions of blocks; prefer hollow shells for huge solids.

## Editing an existing build
If you are given the previous script and a change request, return the COMPLETE updated script (not a
diff), keeping everything the user did not ask to change.
"""


DEFAULT_SITES = [
    "minecraft-schematics.com",
    "abfielder.com",
    "market.phantom-node.com",
    "mineschematic.com",
]


def research_brief(sites, editing=False):
    site_list = "\n".join(f"- {s}" for s in sites)
    what = "the change being asked for" if editing else "this request"
    return f"""## Research first (required)
Before writing the script, look at how real Minecraft builders have made builds like {what}. These schematic
sites have the best builds, so search them first:
{site_list}

1. Use WebSearch (pass allowed_domains with the sites above, or add "site:<domain>" to the query) to find
   3-6 builds that match the request's subject, style and scale. Try two or three different phrasings. If
   the sites have nothing close, do one general web search for Minecraft builds of the subject.
2. Use WebFetch on the 2-4 most relevant build pages. Note each one's dimensions, block palette, shape and
   silhouette, standout details (roof styles, towers, interiors, landscaping) and what makes it look good.
3. Then design an ORIGINAL build that uses what you learned. Do not copy anyone's build block for block.
Keep research short: no more than 5 searches and 5 fetches.

Your reply must contain, in this order:
- a one-line title
- a ```json block listing what you used: [{{"title": "...", "url": "...", "site": "...",
  "size": "e.g. 40x30x35 or unknown", "takeaways": "what you borrowed from it, one sentence"}}]
- the ```python build script
"""


def user_message(prompt, size="medium", palette="auto", previous_code=None, has_image=False,
                 research_sites=None, palette_text=None):
    parts = []
    if previous_code:
        parts.append("Here is the current build script:\n```python\n" + previous_code + "\n```\n")
        parts.append("Change request: " + prompt.strip())
    else:
        parts.append("Build request: " + (prompt.strip() or "Recreate the attached image as a 3D build."))
    if has_image:
        parts.append("Reference image attached: reconstruct it as a real 3D Minecraft structure "
                     "(not flat pixel art, unless it is clearly flat art), matching its colours and shapes.")
    if not previous_code:
        parts.append("Target size: " + SIZES.get(size, SIZES["medium"]) + ".")
    pal = palette_text or PALETTES.get(palette)
    if pal and palette != "auto":
        parts.append("Palette: " + pal)
    if research_sites:
        parts.append(research_brief(research_sites, editing=bool(previous_code)))
    return "\n\n".join(parts)


def fix_message(error):
    return ("The script failed when it ran:\n```\n" + error + "\n```\n"
            "Fix it and reply with the complete corrected script in one ```python block.")
