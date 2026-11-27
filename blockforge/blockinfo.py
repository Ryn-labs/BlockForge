"""What a block is and how it behaves: shape, support, light, gravity and its valid properties.

info("minecraft:oak_stairs[facing=east]") -> dict, explain(state) -> one plain sentence.
Rules are tables by family plus suffix rules, kept consistent with checks.py (solidity) and placement.py (support).
"""
from . import checks

HORIZ = ["north", "south", "east", "west"]
BOOL = ["true", "false"]
SIDES_BOOL = {d: BOOL for d in ("north", "east", "south", "west")}
SIDES_WALL = {d: ["none", "low", "tall"] for d in ("north", "east", "south", "west")}
ROT = [str(i) for i in range(16)]

# ---- property tables by family
PROPS = {
    "stairs": {"facing": HORIZ, "half": ["bottom", "top"],
               "shape": ["straight", "inner_left", "inner_right", "outer_left", "outer_right"], "waterlogged": BOOL},
    "slab": {"type": ["bottom", "top", "double"], "waterlogged": BOOL},
    "door": {"facing": HORIZ, "half": ["lower", "upper"], "hinge": ["left", "right"], "open": BOOL, "powered": BOOL},
    "trapdoor": {"facing": HORIZ, "half": ["bottom", "top"], "open": BOOL, "powered": BOOL, "waterlogged": BOOL},
    "fence": dict(SIDES_BOOL, waterlogged=BOOL),
    "fence_gate": {"facing": HORIZ, "in_wall": BOOL, "open": BOOL, "powered": BOOL},
    "wall": dict(SIDES_WALL, up=BOOL, waterlogged=BOOL),
    "pane": dict(SIDES_BOOL, waterlogged=BOOL),
    "lantern": {"hanging": BOOL, "waterlogged": BOOL},
    "torch": {},
    "wall_torch": {"facing": HORIZ},
    "log": {"axis": ["x", "y", "z"]},
    "leaves": {"distance": [str(i) for i in range(1, 8)], "persistent": BOOL, "waterlogged": BOOL},
    "sign": {"rotation": ROT, "waterlogged": BOOL},
    "wall_sign": {"facing": HORIZ, "waterlogged": BOOL},
    "hanging_sign": {"rotation": ROT, "attached": BOOL, "waterlogged": BOOL},
    "wall_hanging_sign": {"facing": HORIZ, "waterlogged": BOOL},
    "ladder": {"facing": HORIZ, "waterlogged": BOOL},
    "button": {"face": ["floor", "wall", "ceiling"], "facing": HORIZ, "powered": BOOL},
    "chest": {"facing": HORIZ, "type": ["single", "left", "right"], "waterlogged": BOOL},
    "bed": {"facing": HORIZ, "part": ["head", "foot"], "occupied": BOOL},
    "campfire": {"facing": HORIZ, "lit": BOOL, "signal_fire": BOOL, "waterlogged": BOOL},
    "candle": {"candles": ["1", "2", "3", "4"], "lit": BOOL, "waterlogged": BOOL},
    "snow": {"layers": [str(i) for i in range(1, 9)]},
    "vine": {"up": BOOL, "north": BOOL, "east": BOOL, "south": BOOL, "west": BOOL},
    "chain": {"axis": ["x", "y", "z"], "waterlogged": BOOL},
    "furnace": {"facing": HORIZ, "lit": BOOL},
    "banner": {"rotation": ROT},
    "wall_banner": {"facing": HORIZ},
    "carpet": {}, "plant": {}, "full": {}, "other": {},
}

# ---- light emitted when placed (property overrides handled in _light)
LIGHT = {
    "torch": 14, "wall_torch": 14, "soul_torch": 10, "soul_wall_torch": 10, "redstone_torch": 7, "redstone_wall_torch": 7,
    "lantern": 15, "soul_lantern": 10, "glowstone": 15, "sea_lantern": 15, "shroomlight": 15, "jack_o_lantern": 15,
    "campfire": 15, "soul_campfire": 10, "end_rod": 14, "ochre_froglight": 15, "pearlescent_froglight": 15,
    "verdant_froglight": 15, "beacon": 15, "conduit": 15, "lava": 15, "fire": 15, "soul_fire": 10, "magma_block": 3,
    "crying_obsidian": 10, "enchanting_table": 7, "glow_lichen": 7, "sea_pickle": 6, "sculk_catalyst": 6,
    "brewing_stand": 1, "dragon_egg": 1, "end_portal_frame": 1,
}
LIT_LIGHT = {"furnace": 13, "blast_furnace": 13, "smoker": 13, "redstone_lamp": 15, "redstone_ore": 9,
             "deepslate_redstone_ore": 9, "copper_bulb": 15, "exposed_copper_bulb": 12, "weathered_copper_bulb": 8,
             "oxidized_copper_bulb": 4}

GRAVITY_NAMES = {"sand", "red_sand", "gravel", "suspicious_sand", "suspicious_gravel", "anvil", "chipped_anvil",
                 "damaged_anvil", "dragon_egg"}

PLANT_SUFFIX = ("_sapling", "_flower", "_tulip", "_bush", "_mushroom", "_fungus", "_roots", "_orchid", "_petals")
PLANT_NAMES = {"short_grass", "tall_grass", "fern", "large_fern", "dandelion", "poppy", "allium", "azure_bluet",
               "oxeye_daisy", "cornflower", "lily_of_the_valley", "wither_rose", "torchflower", "pitcher_plant",
               "sunflower", "lilac", "rose_bush", "peony", "azalea", "flowering_azalea", "sweet_berry_bush",
               "dead_bush", "bamboo", "sugar_cane", "cactus", "wheat", "carrots", "potatoes", "beetroots", "lily_pad",
               "short_dry_grass", "tall_dry_grass", "bush", "firefly_bush", "seagrass", "kelp", "brown_mushroom",
               "red_mushroom", "melon_stem", "pumpkin_stem", "bamboo_sapling", "pink_petals", "wildflowers",
               "leaf_litter"}
PILLARS = {"bamboo_block", "hay_block", "basalt", "polished_basalt", "bone_block", "purpur_pillar", "quartz_pillar"}

ATTACH = {
    "below": "the top of the block below it",
    "above": "the underside of the block above it",
    "side": "the side of a solid block next to it",
    "none": "",
}


def kind(n):
    """Family key (a PROPS key) for a bare block name. Longer suffixes are tested before the shorter ones they contain."""
    for suffix, fam in (("_wall_hanging_sign", "wall_hanging_sign"), ("_wall_sign", "wall_sign"),
                        ("_hanging_sign", "hanging_sign"), ("_wall_banner", "wall_banner"),
                        ("_wall_torch", "wall_torch"), ("_stairs", "stairs"), ("_slab", "slab"),
                        ("_fence_gate", "fence_gate"), ("_fence", "fence"), ("_wall", "wall"),
                        ("_trapdoor", "trapdoor"), ("_door", "door"), ("_pane", "pane"), ("_bars", "pane")):
        if n.endswith(suffix):
            return fam
    if n == "wall_torch":
        return "wall_torch"
    if n.endswith("lantern") and not n.startswith("sea_") and n != "jack_o_lantern":
        return "lantern"
    if n.endswith("torch"):
        return "torch"
    if n.endswith(("_log", "_wood", "_stem", "_hyphae")) or n in PILLARS:
        return "log"
    if n.endswith("_leaves"):
        return "leaves"
    if n.endswith("_sign"):
        return "sign"
    if n.endswith("_button") or n == "lever":
        return "button"
    if n.endswith("_bed"):
        return "bed"
    if n.endswith("campfire"):
        return "campfire"
    if n.endswith("candle"):
        return "candle"
    if n.endswith("_banner"):
        return "banner"
    if n.endswith("_carpet"):
        return "carpet"
    fam = {"ladder": "ladder", "chest": "chest", "trapped_chest": "chest", "snow": "snow", "vine": "vine",
           "chain": "chain", "furnace": "furnace", "blast_furnace": "furnace", "smoker": "furnace",
           "iron_bars": "pane"}.get(n)
    if fam:
        return fam
    if n in PLANT_NAMES or n.endswith(PLANT_SUFFIX):
        return "plant"
    return "full" if checks.is_solid(n) else "other"


SHAPE_OF = {"stairs": "stairs", "slab": "slab", "door": "door", "trapdoor": "trapdoor", "fence": "fence",
            "fence_gate": "fence", "wall": "wall", "pane": "pane", "lantern": "lantern", "torch": "torch",
            "wall_torch": "torch", "sign": "sign", "wall_sign": "sign", "hanging_sign": "sign",
            "wall_hanging_sign": "sign", "carpet": "carpet", "plant": "plant", "full": "full", "log": "full",
            "leaves": "full"}


def _support(n, k, p):
    """needs_support for a block: 'below', 'side', 'above' or 'none' (matches the rules in placement.py)."""
    if k in ("wall_torch", "ladder", "wall_sign", "wall_hanging_sign", "wall_banner") or n in ("tripwire_hook", "cocoa"):
        return "side"
    if k == "button":
        face = p.get("face", "wall" if n == "lever" else "wall")
        return {"ceiling": "above", "floor": "below"}.get(face, "side")
    if k == "lantern":
        return "above" if p.get("hanging") == "true" else "below"
    if k == "hanging_sign":
        return "above"
    if k == "vine":
        return "side"
    if k in ("door", "torch", "sign", "banner", "carpet", "plant", "candle", "snow"):
        return "below"
    if n in GRAVITY_NAMES or n.endswith("_concrete_powder"):
        return "below"
    if n.endswith(("_pressure_plate", "rail")) or n in ("redstone_wire", "repeater", "comparator", "cake", "flower_pot"):
        return "below"
    return "none"


def _light(n, p):
    if n == "light":
        return int(p.get("level", 15))
    if n.endswith("candle"):
        return 3 * int(p.get("candles", 1)) if p.get("lit") == "true" else 0
    if n in LIT_LIGHT:
        return LIT_LIGHT[n] if p.get("lit") == "true" else 0
    if n.endswith("campfire") and p.get("lit") == "false":
        return 0
    return LIGHT.get(n, 0)


def info(block_state):
    """Facts about one block state; unknown blocks come back as shape 'other' with no properties."""
    n, p = checks.name(block_state), checks.props(block_state)
    k = kind(n)
    sup = _support(n, k, p)
    return {
        "id": "minecraft:" + n,
        "solid": checks.is_solid(block_state),
        "shape": SHAPE_OF.get(k, "other"),
        "family": k,
        "needs_support": sup,
        "attaches_to": ATTACH[sup],
        "light": _light(n, p),
        "gravity": n in GRAVITY_NAMES or n.endswith("_concrete_powder"),
        "properties": {a: list(v) for a, v in PROPS.get(k, {}).items()},
        "given": p,
    }


def check_properties(block_state):
    """Property names or values on this state that the family does not allow (empty list = fine, or family unknown)."""
    d = info(block_state)
    if d["family"] in ("other", "full"):
        return []
    return [f"{a}={v}" for a, v in d["given"].items() if v not in d["properties"].get(a, [])]


def explain(block_state):
    """One plain sentence about the block."""
    d = info(block_state)
    words = d["id"].split(":", 1)[1].replace("_", " ")
    bits = ["a full solid block" if d["solid"] else "not a full block" if d["shape"] == "other" else f"a {d['shape']}"]
    if d["gravity"]:
        bits.append("it falls if there is nothing below it")
    elif d["needs_support"] != "none":
        bits.append(f"it needs {ATTACH[d['needs_support']]} or it pops off")
    if d["light"]:
        bits.append(f"it gives light level {d['light']}")
    props = [f"{a} ({'/'.join(v) if len(v) <= 5 else v[0] + '-' + v[-1]})"
             for a, v in d["properties"].items() if a != "waterlogged"]
    if props:
        bits.append("you can set " + ", ".join(props))
    return f"{words.capitalize()} is " + "; ".join(bits) + "."
