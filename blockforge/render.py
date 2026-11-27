"""Flat block-colour elevations as PNG, for the build tools. Pure Python (zlib only): the installed app has no Pillow.

Colour tables are ported from static/blocks.js (blockColor) so the pictures match the 3D preview."""
import struct
import zlib

DYES = {
    "white": 0xe9ecec, "orange": 0xf07613, "magenta": 0xbd44b3, "light_blue": 0x3aafd9, "yellow": 0xf8c627,
    "lime": 0x70b919, "pink": 0xed8dac, "gray": 0x3e4447, "light_gray": 0x8e8e86, "cyan": 0x158991,
    "purple": 0x792aac, "blue": 0x35399d, "brown": 0x724728, "green": 0x546d1b, "red": 0xa12722,
    "black": 0x141519,
}
CONCRETE = {
    "white": 0xcfd5d6, "orange": 0xe06100, "magenta": 0xa9309f, "light_blue": 0x2389c6, "yellow": 0xf1af15,
    "lime": 0x5ea818, "pink": 0xd5658e, "gray": 0x36393d, "light_gray": 0x7d7d73, "cyan": 0x157788,
    "purple": 0x64209c, "blue": 0x2c2e8f, "brown": 0x603b1f, "green": 0x495b24, "red": 0x8e2020,
    "black": 0x080a0f,
}
TERRACOTTA = {
    "white": 0xd1b2a1, "orange": 0xa05325, "magenta": 0x95586c, "light_blue": 0x706c8a, "yellow": 0xba8523,
    "lime": 0x677534, "pink": 0xa04d4e, "gray": 0x392a23, "light_gray": 0x876a61, "cyan": 0x575b5b,
    "purple": 0x7a4958, "blue": 0x4a3b5b, "brown": 0x4d3323, "green": 0x4c532a, "red": 0x8f3d2e,
    "black": 0x251610,
}
WOOD = {
    "oak": (0xa2834f, 0x6d5532), "spruce": (0x725430, 0x3b2912), "birch": (0xc0af79, 0xd8d7d2),
    "jungle": (0xa07351, 0x554419), "acacia": (0xa85a32, 0x676157), "dark_oak": (0x42291a, 0x3c2e1a),
    "mangrove": (0x773636, 0x5a4a2d), "cherry": (0xe2b2aa, 0x37212a), "pale_oak": (0xe5dcd8, 0x6d6460),
    "bamboo": (0xc4af51, 0x8a9a37), "crimson": (0x653147, 0x5c1a1e), "warped": (0x2b6963, 0x3a3b4e),
}
LEAF = {"oak": 0x4a7a26, "spruce": 0x3d5e3d, "birch": 0x6a8b3e, "jungle": 0x3f8a1e, "acacia": 0x5f8a1e, "dark_oak": 0x3c6a1e, "mangrove": 0x5a8a2a}
FIXED = {
    "stone": 0x7e7e7e, "cobblestone": 0x7a7a7a, "mossy_cobblestone": 0x6e775f, "stone_bricks": 0x7a7979,
    "mossy_stone_bricks": 0x737a62, "cracked_stone_bricks": 0x767676, "chiseled_stone_bricks": 0x777777,
    "smooth_stone": 0x9e9e9e, "andesite": 0x888888, "polished_andesite": 0x848786, "diorite": 0xbcbcbc,
    "polished_diorite": 0xc1c1c3, "granite": 0x956755, "polished_granite": 0x9a6a59, "deepslate": 0x505053,
    "cobbled_deepslate": 0x4d4d51, "polished_deepslate": 0x484849, "deepslate_bricks": 0x464646,
    "cracked_deepslate_bricks": 0x404040, "deepslate_tiles": 0x363637, "cracked_deepslate_tiles": 0x343434,
    "chiseled_deepslate": 0x363636, "tuff": 0x6c6d66, "polished_tuff": 0x626866, "tuff_bricks": 0x62665f,
    "chiseled_tuff": 0x5c605a, "calcite": 0xdfe0dc, "dripstone_block": 0x866b5c, "blackstone": 0x2a2328,
    "polished_blackstone": 0x35303b, "polished_blackstone_bricks": 0x302a32,
    "cracked_polished_blackstone_bricks": 0x2c2529, "gilded_blackstone": 0x382b26, "basalt": 0x505055,
    "polished_basalt": 0x636366, "smooth_basalt": 0x48484e, "bricks": 0x966153, "mud_bricks": 0x89684f,
    "packed_mud": 0x8e6b50, "mud": 0x3c393d, "dirt": 0x866043, "coarse_dirt": 0x775538,
    "rooted_dirt": 0x90674c, "podzol": 0x5c3f18, "grass_block": 0x6a9b3e, "dirt_path": 0x947a41,
    "farmland": 0x52341b, "mycelium": 0x6f6265, "moss_block": 0x596d2d, "moss_carpet": 0x596d2d,
    "sand": 0xdbcfa3, "red_sand": 0xbe6621, "gravel": 0x837f7e, "clay": 0xa0a6b3, "sandstone": 0xd8cb9b,
    "cut_sandstone": 0xd9ce9f, "smooth_sandstone": 0xe0d6aa, "chiseled_sandstone": 0xd8ca9b,
    "red_sandstone": 0xb5621f, "cut_red_sandstone": 0xbd6520, "smooth_red_sandstone": 0xb5621f,
    "terracotta": 0x985e43, "snow_block": 0xf9fefe, "snow": 0xf9fefe, "powder_snow": 0xf8fdfd,
    "ice": 0x91b7fd, "packed_ice": 0x8db4fa, "blue_ice": 0x74a8fd, "obsidian": 0x0f0b19,
    "crying_obsidian": 0x200a3c, "netherrack": 0x612626, "nether_bricks": 0x2c1519,
    "red_nether_bricks": 0x450709, "cracked_nether_bricks": 0x281417, "chiseled_nether_bricks": 0x2f171b,
    "nether_wart_block": 0x720b0b, "warped_wart_block": 0x167679, "soul_sand": 0x513e32,
    "soul_soil": 0x4b3a2e, "glowstone": 0xfbda74, "shroomlight": 0xf09a4b, "sea_lantern": 0xacc7be,
    "magma_block": 0x8e3f1f, "end_stone": 0xdbde9e, "end_stone_bricks": 0xdae0a2, "purpur_block": 0xa97ea9,
    "purpur_pillar": 0xab81ab, "prismarine": 0x639c97, "prismarine_bricks": 0x63ab9e,
    "dark_prismarine": 0x335b4b, "quartz_block": 0xebe5de, "smooth_quartz": 0xece6df,
    "quartz_bricks": 0xeae4dd, "quartz_pillar": 0xebe6e0, "chiseled_quartz_block": 0xe7e2da,
    "amethyst_block": 0x8562bf, "budding_amethyst": 0x8462bf, "copper_block": 0xc06c50,
    "cut_copper": 0xbf6b51, "exposed_copper": 0xa17e68, "exposed_cut_copper": 0x9b7a65,
    "weathered_copper": 0x6c996e, "weathered_cut_copper": 0x6d9170, "oxidized_copper": 0x52a385,
    "oxidized_cut_copper": 0x4f997e, "iron_block": 0xdcdcdc, "gold_block": 0xf6d03d,
    "diamond_block": 0x62ede4, "emerald_block": 0x2acb57, "lapis_block": 0x1f438c,
    "redstone_block": 0xaf1805, "coal_block": 0x101010, "netherite_block": 0x423d3f,
    "raw_iron_block": 0xa6876b, "raw_gold_block": 0xdda92e, "raw_copper_block": 0x9a6a4f,
    "bookshelf": 0x6f5a3b, "chiseled_bookshelf": 0x6f5a3b, "crafting_table": 0x77583a, "furnace": 0x6e6e6e,
    "blast_furnace": 0x515051, "smoker": 0x56493b, "barrel": 0x8a6538, "chest": 0xa77a32,
    "trapped_chest": 0xa77a32, "ender_chest": 0x253537, "hay_block": 0xa68b0c, "pumpkin": 0xc6761c,
    "carved_pumpkin": 0xc6761c, "jack_o_lantern": 0xd6902a, "melon": 0x6f9123, "sponge": 0xc4c04a,
    "slime_block": 0x6fc05a, "honey_block": 0xfbb931, "honeycomb_block": 0xe5941e, "bone_block": 0xe1ddc9,
    "target": 0xe2aa9e, "note_block": 0x58392a, "jukebox": 0x5e402e, "tnt": 0xb5462c, "beacon": 0x75dcd7,
    "lantern": 0xf4bd5d, "soul_lantern": 0x5ec7d1, "torch": 0xffd36b, "wall_torch": 0xffd36b,
    "soul_torch": 0x6ed8e3, "redstone_torch": 0xd33a1a, "campfire": 0xf0a040, "soul_campfire": 0x5ec7d1,
    "chain": 0x3f4553, "iron_bars": 0x8b8d8d, "lightning_rod": 0xc06c50, "bell": 0xf3c13b,
    "anvil": 0x444444, "cauldron": 0x3f3f3f, "water_cauldron": 0x3f3f3f, "grindstone": 0x8c8c8c,
    "stonecutter": 0x7b7672, "lectern": 0xa47f4c, "loom": 0x8e7656, "cartography_table": 0x5a4433,
    "fletching_table": 0xb8a774, "smithing_table": 0x3a3b47, "enchanting_table": 0x5e1d1e,
    "brewing_stand": 0x7a6a50, "flower_pot": 0x7c4536, "water": 0x3f76e4, "lava": 0xd46b17,
    "glass": 0xc6e2ea, "glass_pane": 0xc6e2ea, "tinted_glass": 0x2c272f, "short_grass": 0x6a9b3e,
    "tall_grass": 0x6a9b3e, "fern": 0x5d8a3a, "large_fern": 0x5d8a3a, "dead_bush": 0x7b5b2b,
    "vine": 0x3f7d22, "glow_lichen": 0x70827a, "sugar_cane": 0x93c05a, "bamboo": 0x6f9a2c,
    "cactus": 0x5a8a2c, "kelp": 0x5a8a2c, "lily_pad": 0x2a7d33, "poppy": 0xc0262a, "dandelion": 0xf2d43a,
    "cornflower": 0x4a6be0, "allium": 0xb57ae0, "azure_bluet": 0xd8e4f0, "blue_orchid": 0x2aa7e0,
    "oxeye_daisy": 0xe9ecd8, "lily_of_the_valley": 0xf0f0f0, "red_tulip": 0xd03a2a,
    "orange_tulip": 0xe07a2a, "white_tulip": 0xe8e8e8, "pink_tulip": 0xe8a0c0, "sunflower": 0xf6c62a,
    "rose_bush": 0xb52a2a, "peony": 0xe0a8d8, "lilac": 0xc49ad0, "wither_rose": 0x2a2a20,
    "torchflower": 0xe28a3a, "pink_petals": 0xf3a6c8, "spore_blossom": 0xd66a9a, "azalea": 0x667f30,
    "flowering_azalea": 0x8c6f9a, "sweet_berry_bush": 0x3a6a2a, "brown_mushroom": 0x997257,
    "red_mushroom": 0xd83a2f, "brown_mushroom_block": 0x957051, "red_mushroom_block": 0xc82f2c,
    "mushroom_stem": 0xcbc4b9, "cobweb": 0xe4e8ea, "scaffolding": 0xae8b4e, "ladder": 0x7f6438,
    "rail": 0x7f7563, "powered_rail": 0x9a7e44, "sculk": 0x0d1d24, "sculk_sensor": 0x0d5a63,
    "ochre_froglight": 0xf6e9a5, "verdant_froglight": 0xe5f4e2, "pearlescent_froglight": 0xf4e9ee,
    "resin_block": 0xd6681a, "resin_bricks": 0xc85a16, "copper_bulb": 0xc06c50, "crafter": 0x6e6262,
    "decorated_pot": 0x8c4e3e, "candle": 0xe7d5b0, "white_candle": 0xe0e3e3, "respawn_anchor": 0x2b1f43,
    "lodestone": 0x7a7b7e, "structure_void": 0xffffff, "barrier": 0xff0000, "light": 0xffff99,
    "bedrock": 0x555555, "sea_pickle": 0x6b7a31, "coral_block": 0x3150c8, "dried_kelp_block": 0x323b29,
    "cherry_leaves": 0xe9a3c4, "azalea_leaves": 0x5b7a2e, "flowering_azalea_leaves": 0x76784a,
    "pale_oak_leaves": 0x8b938a, "mangrove_roots": 0x4a3a28, "muddy_mangrove_roots": 0x463b2d,
    "pale_moss_block": 0x6b746a, "pale_moss_carpet": 0x6b746a, "creaking_heart": 0x4f4642,
    "heavy_core": 0x50525a, "trial_spawner": 0x2f4552, "vault": 0x3a4448, "spawner": 0x2a3a48,
    "end_rod": 0xf0e8e0, "conduit": 0x9a8a6a, "dragon_egg": 0x0c0910, "player_head": 0x6e4b30,
    "skeleton_skull": 0xc8c8c8, "armor_stand": 0x9a7a4a, "redstone_wire": 0xb01208, "repeater": 0xa9a49e,
    "comparator": 0xb3aca5, "observer": 0x5f5f5f, "piston": 0x9d8a68, "sticky_piston": 0x7fa060,
    "redstone_lamp": 0x8a5a33, "hopper": 0x3e3e42, "dropper": 0x707070, "dispenser": 0x6d6d6d,
    "daylight_detector": 0xc2ad86, "lever": 0x6e5a3c, "tripwire_hook": 0x8a7b6a, "detector_rail": 0x8a7563,
    "activator_rail": 0x8a6a5e, "redstone_ore": 0x8a6b6b,
}

_cache = {}
_SHAPES = ("_stairs", "_slab", "_wall", "_fence_gate", "_fence", "_pressure_plate", "_button", "_trapdoor", "_door")


def _lighten(c, f):
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    return (min(255, round(r + (255 - r) * f)) << 16) | (min(255, round(g + (255 - g) * f)) << 8) | min(255, round(b + (255 - b) * f))


def _dye(name):
    if "sandstone" in name or "nether" in name or "mushroom" in name:
        return None                                  # red_sandstone, red_nether_bricks ... are not dyed blocks
    for d in ["light_blue", "light_gray"] + list(DYES):
        if name.startswith(d + "_"):
            return d
    return None


def _compute(name):
    if name in FIXED:
        return FIXED[name]
    dye = _dye(name)
    if dye:
        if "concrete_powder" in name:
            return _lighten(CONCRETE[dye], 0.12)
        if "concrete" in name:
            return CONCRETE[dye]
        if "glazed_terracotta" in name:
            return _lighten(TERRACOTTA[dye], 0.15)
        if "terracotta" in name:
            return TERRACOTTA[dye]
        return DYES[dye]
    if name.startswith("potted_"):
        return FIXED["flower_pot"]
    if name.endswith("_leaves"):
        return next((v for w, v in LEAF.items() if name.startswith(w)), 0x4a7a26)
    for w in ["dark_oak", "pale_oak"] + list(WOOD):
        if w in name:
            plank, bark = WOOD[w]
            if name.startswith("stripped_"):
                return plank
            return bark if name.endswith(("_log", "_wood", "_stem", "_hyphae")) else plank
    if "mossy" in name:
        return 0x6e775f
    base = name
    for suf in _SHAPES:
        if base.endswith(suf):
            base = base[:-len(suf)]
            break
    for cand in (base, base + "s", base + "_block", base.replace("brick", "bricks"), base.replace("tile", "tiles"),
                 base.replace("waxed_", "", 1), base.replace("waxed_", "", 1) + "_block", base.replace("smooth_", "")):
        if cand != name and cand in FIXED:
            return FIXED[cand]
    for word, col in (("oxidized", 0x52a385), ("weathered", 0x6c996e), ("exposed", 0xa17e68), ("copper", 0xc06c50),
                      ("quartz", 0xebe5de), ("blackstone", 0x302a32), ("deepslate", 0x464646), ("prismarine", 0x63ab9e),
                      ("nether", 0x2c1519), ("purpur", 0xa97ea9), ("end_stone", 0xdae0a2), ("ore", 0x7e7e7e),
                      ("coral", 0xc84a7a), ("iron", 0xa8a8a8), ("stone", 0x7e7e7e)):
        if word in name:
            if word == "sandstone":
                return 0xb5621f if "red" in name else 0xd8cb9b
            return col
    if "sandstone" in name:
        return 0xb5621f if "red" in name else 0xd8cb9b
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return ((96 + (h & 63)) << 16) | ((96 + ((h >> 6) & 63)) << 8) | (96 + ((h >> 12) & 63))


def block_color(state):
    """RGB tuple for a block state like 'minecraft:oak_stairs[facing=north]'."""
    name = state.split("[", 1)[0]
    name = name.split(":", 1)[-1]
    c = _cache.get(name)
    if c is None:
        c = _cache[name] = _compute(name)
    return (c >> 16) & 255, (c >> 8) & 255, c & 255


# ------------------------------------------------------------------ PNG
def png_bytes(width, height, pixels):
    """pixels: bytes/bytearray of width*height*3 RGB values."""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


# ------------------------------------------------------------------ elevations
SIDES = ("north", "east", "south", "west", "top")
MAX_PX = 512
BG = (28, 31, 38)
GRID = (44, 48, 58)


def _view_axes(side):
    """(horizontal axis index, flip horizontal, vertical axis index, flip vertical, depth axis index, depth sign)
    Depth sign +1 means larger values are nearer the viewer. Axes: 0 x(east), 1 y(up), 2 z(south)."""
    return {
        "south": (0, False, 1, True, 2, 1),      # viewer south of the build looking north: east is on the right
        "north": (0, True, 1, True, 2, -1),      # viewer north looking south: east is on the left
        "east": (2, True, 1, True, 0, 1),        # viewer east looking west: north is on the right
        "west": (2, False, 1, True, 0, -1),      # viewer west looking east: south is on the right
        "top": (0, False, 2, False, 1, 1),       # from above, north at the top
    }[side]


def nearest(blocks, side):
    """One elevation as data: {(across, up): (nearness, (x, y, z), state)}, the block seen in each cell of the view
    from `side` (nearness grows towards the viewer). render_side draws it; quality.py measures the colours on it."""
    if side not in SIDES:
        raise ValueError("side must be one of " + ", ".join(SIDES))
    ha, hflip, va, vflip, da, dsign = _view_axes(side)
    best = {}
    for p, st in blocks.items():
        key = (p[ha], p[va])
        near = p[da] * dsign
        cur = best.get(key)
        if cur is None or near > cur[0]:
            best[key] = (near, p, st)
    return best


def render_side(blocks, side):
    """PNG bytes of one flat elevation: the nearest block in each column, darker the further back it is."""
    if side not in SIDES:
        raise ValueError("side must be one of " + ", ".join(SIDES))
    ha, hflip, va, vflip, da, dsign = _view_axes(side)
    lo = [min(p[i] for p in blocks) for i in range(3)]
    hi = [max(p[i] for p in blocks) for i in range(3)]
    w, h = hi[ha] - lo[ha] + 1, hi[va] - lo[va] + 1
    depth = hi[da] - lo[da] + 1
    best = {k: (v[0], v[2]) for k, v in nearest(blocks, side).items()}
    cell = max(1, min(32, (MAX_PX - 2) // max(w, h)))
    while cell > 1 and (w * cell + 2 > MAX_PX or h * cell + 2 > MAX_PX):
        cell -= 1
    scale = 1
    if w * cell + 2 > MAX_PX or h * cell + 2 > MAX_PX:        # a very large build: sample every n-th block
        scale = -(-max(w, h) // (MAX_PX - 2))
    cw, ch = (w + scale - 1) // scale * cell, (h + scale - 1) // scale * cell
    W, H = cw + 2, ch + 2
    pix = bytearray(BG * (W * H))
    front = max((v[0] for v in best.values()), default=0)
    for (a, b), (near, st) in best.items():
        cx = a - lo[ha]
        cy = b - lo[va]
        if hflip:
            cx = w - 1 - cx
        if vflip:
            cy = h - 1 - cy
        if cx % scale or cy % scale:
            continue
        cx //= scale
        cy //= scale
        r, g, bl = block_color(st)
        fade = 1.0 - 0.45 * min(1.0, (front - near) / max(1, depth))      # farther back = darker
        col = bytes((int(r * fade), int(g * fade), int(bl * fade)))
        edge = bytes((int(r * fade * 0.8), int(g * fade * 0.8), int(bl * fade * 0.8)))
        for yy in range(cell):
            row = ((1 + cy * cell + yy) * W + 1 + cx * cell) * 3
            for xx in range(cell):
                pix[row + xx * 3:row + xx * 3 + 3] = edge if cell >= 4 and (xx == cell - 1 or yy == cell - 1) else col
    return png_bytes(W, H, pix)
