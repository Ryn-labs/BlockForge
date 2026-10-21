"""Export a build to .schem (WorldEdit), .litematic (Litematica), .nbt (structure block) and
.mcstructure (Bedrock), and import .schem / .litematic / .nbt files back into a build."""
import time

from . import nbt
from .nbt import BYTE, SHORT, INT, LONG, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY, BYTE_ARRAY

DATA_VERSION = 3955          # Java 1.21.1 (newer versions load it fine)
AIR = "minecraft:air"
FORMATS = {
    "schem": ("WorldEdit / FAWE (.schem)", ".schem"),
    "litematic": ("Litematica (.litematic)", ".litematic"),
    "nbt": ("Structure block (.nbt)", ".nbt"),
    "mcstructure": ("Bedrock structure (.mcstructure)", ".mcstructure"),
}


def parse_state(st):
    if "[" not in st:
        return st, {}
    name, rest = st.split("[", 1)
    props = {}
    for kv in rest.rstrip("]").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            props[k.strip()] = v.strip()
    return name, props


def state_str(name, props):
    if not name.startswith("minecraft:") and ":" not in name:
        name = "minecraft:" + name
    if props:
        return name + "[" + ",".join(f"{k}={v}" for k, v in sorted(props.items())) + "]"
    return name


# ------------------------------------------------------------------ build <-> plain data
def to_dict(blocks, tiles=None):
    """blocks: {(x,y,z): state} with any coords -> compact dict normalised to 0..size-1.
    tiles: {(x,y,z): {"id", "items": [{"slot", "id", "count", "name"?}], "name"?}} container contents (kept only where
    that container still is)."""
    if not blocks:
        return {"size": [1, 1, 1], "palette": [], "blocks": []}
    xs = [p[0] for p in blocks]
    ys = [p[1] for p in blocks]
    zs = [p[2] for p in blocks]
    mx, my, mz = min(xs), min(ys), min(zs)
    size = [max(xs) - mx + 1, max(ys) - my + 1, max(zs) - mz + 1]
    pal = {}
    flat = []
    for (x, y, z), st in sorted(blocks.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        i = pal.setdefault(st, len(pal))
        flat += [x - mx, y - my, z - mz, i]
    out = {"size": size, "palette": list(pal), "blocks": flat}
    if tiles:
        out["tiles"] = [[x - mx, y - my, z - mz, t] for (x, y, z), t in sorted(tiles.items())
                        if blocks.get((x, y, z), "").split("[", 1)[0] == t.get("id")]
    return out


ITEM_COMPONENTS_DV = 3837       # 1.20.5: items use "count" + components instead of "Count" + tag


def _text(s):
    import json
    return json.dumps({"text": str(s)})


def _item_nbt(it, dv):
    e = {"Slot": (BYTE, int(it.get("slot", 0))), "id": (STRING, it["id"])}
    if dv >= ITEM_COMPONENTS_DV:
        e["count"] = (INT, int(it.get("count", 1)))
        if it.get("name"):
            e["components"] = (COMPOUND, {"minecraft:custom_name": (STRING, _text(it["name"]))})
    else:
        e["Count"] = (BYTE, int(it.get("count", 1)))
        if it.get("name"):
            e["tag"] = (COMPOUND, {"display": (COMPOUND, {"Name": (STRING, _text(it["name"]))})})
    return e


def tile_nbt(t, dv):
    """Block-entity NBT fields (without position) for a container."""
    e = {"id": (STRING, t["id"]), "Items": (LIST, (COMPOUND, [_item_nbt(i, dv) for i in t.get("items") or []]))}
    if t.get("name"):
        e["CustomName"] = (STRING, _text(t["name"]))
    return e


def from_dict(d):
    pal = d["palette"]
    f = d["blocks"]
    return {(f[i], f[i + 1], f[i + 2]): pal[f[i + 3]] for i in range(0, len(f), 4)}


# ------------------------------------------------------------------ writers
def write_schem(path, d, name):
    W, H, L = d["size"]
    blocks = from_dict(d)
    palette = {AIR: 0}
    data = bytearray()
    for y in range(H):
        for z in range(L):
            for x in range(W):
                idx = palette.setdefault(blocks.get((x, y, z), AIR), len(palette))
                while idx & ~0x7F:
                    data.append((idx & 0x7F) | 0x80)
                    idx >>= 7
                data.append(idx)
    root = {
        "Version": (INT, 2),
        "DataVersion": (INT, d.get("data_version") or DATA_VERSION),
        "Metadata": (COMPOUND, {"Name": (STRING, name), "Author": (STRING, "BlockForge + Claude"),
                                "WEOffsetX": (INT, 0), "WEOffsetY": (INT, 0), "WEOffsetZ": (INT, 0)}),
        "Width": (SHORT, W), "Height": (SHORT, H), "Length": (SHORT, L),
        "Offset": (INT_ARRAY, [0, 0, 0]),
        "PaletteMax": (INT, len(palette)),
        "Palette": (COMPOUND, {k: (INT, v) for k, v in palette.items()}),
        "BlockData": (BYTE_ARRAY, data),
        "BlockEntities": (LIST, (COMPOUND, [
            {"Pos": (INT_ARRAY, [x, y, z]), "Id": (STRING, t["id"]),
             **{k: v for k, v in tile_nbt(t, d.get("data_version") or DATA_VERSION).items() if k != "id"}}
            for x, y, z, t in d.get("tiles") or []])),
        "Entities": (LIST, (COMPOUND, [])),
    }
    nbt.write(path, "Schematic", root)


def _pal_entry(st):
    n, props = parse_state(st)
    e = {"Name": (STRING, n)}
    if props:
        e["Properties"] = (COMPOUND, {k: (STRING, v) for k, v in props.items()})
    return e


def write_litematic(path, d, name, desc=""):
    W, H, L = d["size"]
    blocks = from_dict(d)
    pal = {AIR: 0}
    vol = W * H * L
    idxs = [0] * vol
    for (x, y, z), st in blocks.items():
        idxs[(y * L + z) * W + x] = pal.setdefault(st, len(pal))
    bits = max(2, (len(pal) - 1).bit_length())
    arr = [0] * ((vol * bits + 63) // 64)
    M64 = (1 << 64) - 1
    for i, v in enumerate(idxs):
        if v:
            start = i * bits
            si, so = start >> 6, start & 63
            arr[si] |= (v << so) & M64
            if so + bits > 64:
                arr[si + 1] |= v >> (64 - so)
    arr = [a - (1 << 64) if a >= (1 << 63) else a for a in arr]

    def pos(x, y, z):
        return (COMPOUND, {"x": (INT, x), "y": (INT, y), "z": (INT, z)})

    empty = (LIST, (COMPOUND, []))
    region = {
        "Position": pos(0, 0, 0), "Size": pos(W, H, L),
        "BlockStatePalette": (LIST, (COMPOUND, [_pal_entry(st) for st in sorted(pal, key=pal.get)])),
        "BlockStates": (LONG_ARRAY, arr),
        "Entities": empty, "PendingBlockTicks": empty, "PendingFluidTicks": empty,
        "TileEntities": (LIST, (COMPOUND, [
            {"x": (INT, x), "y": (INT, y), "z": (INT, z), **tile_nbt(t, d.get("data_version") or DATA_VERSION)}
            for x, y, z, t in d.get("tiles") or []])),
    }
    now = int(time.time() * 1000)
    root = {
        "MinecraftDataVersion": (INT, d.get("data_version") or DATA_VERSION),
        "Version": (INT, 5),
        "Metadata": (COMPOUND, {
            "Name": (STRING, name), "Author": (STRING, "BlockForge + Claude"),
            "Description": (STRING, desc[:500]),
            "RegionCount": (INT, 1), "TotalBlocks": (INT, len(blocks)), "TotalVolume": (INT, vol),
            "TimeCreated": (LONG, now), "TimeModified": (LONG, now), "EnclosingSize": pos(W, H, L)}),
        "Regions": (COMPOUND, {name[:60] or "build": (COMPOUND, region)}),
    }
    nbt.write(path, "", root)


def write_nbt_structure(path, d, name):
    W, H, L = d["size"]
    pal = d["palette"]
    f = d["blocks"]
    dv = d.get("data_version") or DATA_VERSION
    tiles = {(x, y, z): t for x, y, z, t in d.get("tiles") or []}
    blocks = []
    for i in range(0, len(f), 4):
        e = {"pos": (LIST, (INT, [f[i], f[i + 1], f[i + 2]])), "state": (INT, f[i + 3])}
        t = tiles.get((f[i], f[i + 1], f[i + 2]))
        if t:
            e["nbt"] = (COMPOUND, tile_nbt(t, dv))
        blocks.append(e)
    root = {
        "DataVersion": (INT, d.get("data_version") or DATA_VERSION),
        "size": (LIST, (INT, [W, H, L])),
        "palette": (LIST, (COMPOUND, [_pal_entry(st) for st in pal])),
        "blocks": (LIST, (COMPOUND, blocks)),
        "entities": (LIST, (COMPOUND, [])),
    }
    nbt.write(path, "", root)


# --- Bedrock: names mostly match modern Bedrock; translate the common states that differ.
BEDROCK_RENAME = {
    "minecraft:grass_block": "minecraft:grass_block", "minecraft:short_grass": "minecraft:short_grass",
    "minecraft:dirt_path": "minecraft:grass_path", "minecraft:snow_block": "minecraft:snow",
    "minecraft:snow": "minecraft:snow_layer", "minecraft:jack_o_lantern": "minecraft:lit_pumpkin",
    "minecraft:magma_block": "minecraft:magma", "minecraft:nether_bricks": "minecraft:nether_brick",
    "minecraft:red_nether_bricks": "minecraft:red_nether_brick", "minecraft:terracotta": "minecraft:hardened_clay",
    "minecraft:cobweb": "minecraft:web", "minecraft:sugar_cane": "minecraft:reeds",
    "minecraft:oak_sign": "minecraft:standing_sign", "minecraft:oak_wall_sign": "minecraft:wall_sign",
    "minecraft:lily_pad": "minecraft:waterlily", "minecraft:wall_torch": "minecraft:torch",
    "minecraft:end_stone_bricks": "minecraft:end_bricks", "minecraft:spawner": "minecraft:mob_spawner",
    "minecraft:oak_door": "minecraft:wooden_door", "minecraft:oak_trapdoor": "minecraft:trapdoor",
    "minecraft:oak_fence_gate": "minecraft:fence_gate", "minecraft:oak_button": "minecraft:wooden_button",
    "minecraft:oak_pressure_plate": "minecraft:wooden_pressure_plate",
    "minecraft:note_block": "minecraft:noteblock", "minecraft:powered_rail": "minecraft:golden_rail",
}
_DIR4 = {"south": 0, "west": 1, "north": 2, "east": 3}
_STAIR_DIR = {"east": 0, "west": 1, "south": 2, "north": 3}
_TORCH = {"west": "east", "east": "west", "north": "south", "south": "north"}


def _bedrock_state(st):
    name, p = parse_state(st)
    name = BEDROCK_RENAME.get(name, name)
    out = {}
    base = name.split(":", 1)[1]
    if base.endswith("_stairs"):
        out["weirdo_direction"] = (INT, _STAIR_DIR.get(p.get("facing", "north"), 3))
        out["upside_down_bit"] = (BYTE, 1 if p.get("half") == "top" else 0)
    elif base.endswith("_slab"):
        t = p.get("type", "bottom")
        if t == "double":
            name = name.replace("_slab", "_double_slab")
        out["minecraft:vertical_half"] = (STRING, "top" if t == "top" else "bottom")
    elif base.endswith(("_log", "_wood", "_stem", "_hyphae")) or base in ("hay_block", "bone_block", "basalt",
                                                                            "quartz_pillar", "purpur_pillar"):
        out["pillar_axis"] = (STRING, p.get("axis", "y"))
    elif base == "torch" and "facing" in p:
        out["torch_facing_direction"] = (STRING, _TORCH.get(p["facing"], "top"))
    elif base.endswith("_leaves"):
        out["persistent_bit"] = (BYTE, 1)
    elif "facing" in p and base in ("furnace", "chest", "barrel", "carved_pumpkin", "lit_pumpkin", "smoker",
                                    "blast_furnace", "ender_chest", "loom", "stonecutter"):
        out["minecraft:cardinal_direction"] = (STRING, p["facing"] if p["facing"] in _DIR4 else "south")
    elif base in ("lantern", "soul_lantern"):
        out["hanging"] = (BYTE, 1 if p.get("hanging") == "true" else 0)
    elif base == "water" or base == "lava":
        out["liquid_depth"] = (INT, 0)
    return name, out


def write_mcstructure(path, d, name):
    W, H, L = d["size"]
    blocks = from_dict(d)
    palette = {}
    pal_list = []
    idx = []
    for x in range(W):
        for y in range(H):
            for z in range(L):
                st = blocks.get((x, y, z), AIR)
                if st not in palette:
                    palette[st] = len(pal_list)
                    bn, bs = _bedrock_state(st) if st != AIR else ("minecraft:air", {})
                    pal_list.append({"name": (STRING, bn), "states": (COMPOUND, bs), "version": (INT, 18100737)})
                idx.append(palette[st])
    root = {
        "format_version": (INT, 1),
        "size": (LIST, (INT, [W, H, L])),
        "structure": (COMPOUND, {
            "block_indices": (LIST, (LIST, [(INT, idx), (INT, [-1] * len(idx))])),
            "entities": (LIST, (COMPOUND, [])),
            "palette": (COMPOUND, {"default": (COMPOUND, {
                "block_palette": (LIST, (COMPOUND, pal_list)),
                "block_position_data": (COMPOUND, {}),
            })}),
        }),
        "structure_world_origin": (LIST, (INT, [0, 0, 0])),
    }
    nbt.write(path, "", root, little=True, compress=False)


def export(d, fmt, path, name, desc=""):
    if fmt == "schem":
        write_schem(path, d, name)
    elif fmt == "litematic":
        write_litematic(path, d, name, desc)
    elif fmt == "nbt":
        write_nbt_structure(path, d, name)
    elif fmt == "mcstructure":
        write_mcstructure(path, d, name)
    else:
        raise ValueError("unknown format " + fmt)


# ------------------------------------------------------------------ readers
def _read_varints(data):
    out, v, shift = [], 0, 0
    for b in data:
        v |= (b & 0x7F) << shift
        if b & 0x80:
            shift += 7
        else:
            out.append(v)
            v, shift = 0, 0
    return out


def _props_to_state(e):
    return state_str(e["Name"], e.get("Properties", {}))


def import_file(data):
    """Return {(x,y,z): state} from .schem (v2/v3), .litematic or .nbt bytes."""
    root = nbt.loads(data)
    if "Schematic" in root and isinstance(root["Schematic"], dict):
        root = root["Schematic"]                       # Sponge v3 wraps everything
    blocks = {}
    if "Regions" in root:                              # litematic
        for reg in root["Regions"].values():
            sx, sy, sz = (reg["Size"][k] for k in "xyz")
            px, py, pz = (reg["Position"][k] for k in "xyz")
            W, H, L = abs(sx), abs(sy), abs(sz)
            ox, oy, oz = px + min(sx + 1, 0), py + min(sy + 1, 0), pz + min(sz + 1, 0)
            pal = [_props_to_state(e) for e in reg["BlockStatePalette"]]
            bits = max(2, (len(pal) - 1).bit_length())
            arr = [a & ((1 << 64) - 1) for a in reg["BlockStates"]]
            mask = (1 << bits) - 1
            for i in range(W * H * L):
                start = i * bits
                si, so = start >> 6, start & 63
                v = arr[si] >> so
                if so + bits > 64:
                    v |= arr[si + 1] << (64 - so)
                v &= mask
                st = pal[v] if v < len(pal) else AIR
                if not st.startswith("minecraft:air"):
                    x = i % W
                    z = (i // W) % L
                    y = i // (W * L)
                    blocks[(ox + x, oy + y, oz + z)] = st
        return blocks
    if "palette" in root and "blocks" in root and isinstance(root["blocks"], list):   # vanilla structure
        pal = [_props_to_state(e) for e in root["palette"]]
        for b in root["blocks"]:
            st = pal[b["state"]]
            if not st.startswith("minecraft:air") and st != "minecraft:structure_void":
                blocks[tuple(b["pos"])] = st
        return blocks
    if "Width" in root:                                # sponge schem
        W, H, L = root["Width"], root["Height"], root["Length"]
        if "Blocks" in root and isinstance(root["Blocks"], dict):     # v3
            pal_raw, data_raw = root["Blocks"]["Palette"], root["Blocks"]["Data"]
        else:
            pal_raw, data_raw = root["Palette"], root["BlockData"]
        pal = {v: k for k, v in pal_raw.items()}
        for i, v in enumerate(_read_varints(data_raw)):
            st = pal.get(v, AIR)
            if not st.startswith("minecraft:air"):
                x = i % W
                z = (i // W) % L
                y = i // (W * L)
                blocks[(x, y, z)] = st
        return blocks
    raise ValueError("Unrecognised schematic file (supported: .schem, .litematic, .nbt)")
