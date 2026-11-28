"""House check: every building in a build can be walked into, walked through, is lit, roofed and sits on the ground.

findings(blocks, ground=None) -> [(check, (x, y, z), text)] in the form checks.run collects (checks.run adds them, so the
step-by-step check, save_build, the script engine, chat, the MCP review and the bench all get them). `ground` is the
terrain.Ground of a build on terrain (any value that is not None means "the land is part of the build").

Finding the buildings: a standing spot is a floor block with 2 free blocks above it; it is COVERED when a building
block (not land, not leaves) is somewhere above it. Covered spots joined side by side (steps of up to 2 blocks, not
through a door or a 1-wide gap between two wall blocks) form a ROOM when walls close it: looking out from its edge
cells, at most 15% of the sides reach the open sky (a railing, furniture or a low beam does not close a side, the wall
behind it does), and most of it has 3 free blocks above the floor. A room needs a 3 x 3 patch of floor; rooms over each
other (sharing a column) are one building, and a building must have something a house has (a door, a window, a bed,
furniture, a light, or a way in on foot). So statues, bridges, tunnels, verandas, the crawl space under a stilt house,
pixel art and terrain give no building and no findings.

Per building:
  door_unreachable      no door or 2-high opening joins the ground outside on foot: steps up only by a stair or slab
                        (half a block), never a full block, 1.8 blocks of headroom over the higher spot of every step
  interior_unreachable  under 80% of the floor of the storeys the walker reaches (2 high; spots up to 2 above or below
                        that floor count, tables and furniture tops do not) can be walked to from outside
  low_headroom          1-high spots inside next to where people walk (not the nook under a stair they walk on, not a
                        table top); a sealed attic nobody can get into is not counted
  dark_spawn_spot       a floor cell people reach inside with a full top, 2 free blocks and block light 0 (light spread
                        from lanterns, torches, glowstone, ...: walls stop it, slabs and stairs through their solid
                        faces): mobs spawn there. One finding per patch, with a lantern spot
  roof_hole             a patch of up to 12 floor cells inside with open sky above it (not a courtyard, a garden bed, a
                        roof slope, a ladder hatch or a stairwell to the roof)
  wall_over_air         the base of the ground-storey walls hangs 2+ blocks over air with no support or post near it
  land_against_wall     land (dirt, grass, stone, ...) piled 2+ blocks up an outside wall
The ground: the walk areas outside under the open sky (streets, yards, the land), not a balcony or a small roof terrace.
A build without terrain stands on its lowest layer: where that layer is empty the world's ground is assumed level with
it. Pure Python (the app ships without numpy); the session caches checks.run per build content."""
import collections

from . import checks

MAIN_PCT = 80                       # INTERIOR: at least this % of the floor reached
MIN_ROOM = 9                        # floor cells of the smallest building (a 3 x 3 room)
LIGHT_MARGIN = 6                    # light spread is worked out in each building's box plus this margin
EAST, WEST, SOUTH, NORTH, UP, DOWN = range(6)
DXZ = ((1, 0), (-1, 0), (0, 1), (0, -1))
OPP = (1, 0, 3, 2, 5, 4)
DIR_NAME = ("east", "west", "south", "north")
DIR_OF = {"east": 0, "west": 1, "south": 2, "north": 3}

EMPTY = {"air", "cave_air", "void_air", "structure_void", "light"}
PLANTS = {"short_grass", "grass", "tall_grass", "fern", "large_fern", "dead_bush", "vine", "glow_lichen", "seagrass",
          "tall_seagrass", "kelp", "kelp_plant", "sugar_cane", "lever", "redstone_wire", "tripwire", "tripwire_hook",
          "cobweb", "dandelion", "poppy", "blue_orchid", "allium", "azure_bluet", "oxeye_daisy", "cornflower",
          "lily_of_the_valley", "wither_rose", "sunflower", "lilac", "rose_bush", "peony", "torchflower", "pink_petals",
          "brown_mushroom", "red_mushroom", "crimson_fungus", "warped_fungus", "sweet_berry_bush", "bush", "firefly_bush",
          "nether_wart", "wheat", "carrots", "potatoes", "beetroots", "hanging_roots", "spore_blossom", "cave_vines",
          "cave_vines_plant", "weeping_vines", "weeping_vines_plant", "twisting_vines", "twisting_vines_plant", "fire",
          "soul_fire", "pitcher_plant", "short_dry_grass", "tall_dry_grass", "leaf_litter", "wildflowers",
          "cactus_flower", "bamboo_sapling", "nether_sprouts", "crimson_roots", "warped_roots", "sculk_vein",
          "big_dripleaf_stem", "small_dripleaf", "pale_hanging_moss", "resin_clump", "melon_stem", "pumpkin_stem",
          "attached_melon_stem", "attached_pumpkin_stem"}
# land: what the ground is made of (never a building block; plain stone counts, sandstone does not)
LAND = {"stone", "granite", "diorite", "andesite", "tuff", "deepslate", "dirt", "coarse_dirt", "rooted_dirt", "podzol",
        "grass_block", "mycelium", "mud", "clay", "gravel", "sand", "red_sand", "dripstone_block", "moss_block",
        "snow_block", "infested_stone", "netherrack", "magma_block", "bedrock", "dirt_path", "farmland", "calcite",
        "suspicious_gravel", "suspicious_sand", "water", "lava", "bubble_column", "packed_ice", "ice", "blue_ice",
        "powder_snow"}
GARDEN = {"grass_block", "dirt", "coarse_dirt", "rooted_dirt", "podzol", "moss_block", "gravel", "sand", "mud", "water",
          "clay", "dirt_path", "farmland", "mycelium", "moss_carpet"}
LUM = {"lantern": 15, "soul_lantern": 10, "torch": 14, "wall_torch": 14, "soul_torch": 10, "soul_wall_torch": 10,
       "glowstone": 15, "sea_lantern": 15, "jack_o_lantern": 15, "shroomlight": 15, "end_rod": 14,
       "ochre_froglight": 15, "pearlescent_froglight": 15, "verdant_froglight": 15, "lava": 15, "beacon": 15,
       "conduit": 15, "fire": 15, "soul_fire": 10, "glow_lichen": 7, "crying_obsidian": 10, "enchanting_table": 7,
       "ender_chest": 7, "brewing_stand": 1, "magma_block": 3, "amethyst_cluster": 5, "large_amethyst_bud": 4,
       "medium_amethyst_bud": 2, "small_amethyst_bud": 1, "sculk_catalyst": 6, "copper_lantern": 15,
       "exposed_copper_lantern": 15, "weathered_copper_lantern": 15, "oxidized_copper_lantern": 15,
       "copper_torch": 14, "copper_wall_torch": 14}
# full blocks people put in a room as furniture: standing on top of one is not a floor
FURNITURE = {"bookshelf", "chiseled_bookshelf", "crafting_table", "barrel", "furnace", "blast_furnace", "smoker",
             "cartography_table", "fletching_table", "smithing_table", "loom", "jukebox", "note_block", "hay_block",
             "beehive", "bee_nest", "target", "tnt", "pumpkin", "carved_pumpkin", "melon", "dried_kelp_block"}
# a room with one of these is a room people use (a hollow statue has none)
FEATURE_PARTS = ("_door", "glass", "_bed", "chest", "barrel", "crafting_table", "furnace", "smoker", "bookshelf",
                 "lectern", "lantern", "torch", "campfire", "table", "chair", "candle", "cauldron", "anvil", "loom")


def _kind(n, p):
    """Shape family of a block (the walk graph and light spread work on these)."""
    b = n.split(":")[-1]
    mod = ":" in n
    if b in ("water", "lava", "bubble_column"):
        return "liq"
    if b in EMPTY:
        return "empty"
    if "leaves" in b and "pile" not in b:
        return "leaves"
    if b.endswith("_door"):
        return "door"
    if b.endswith("_fence_gate"):
        return "air"
    if b.endswith("_trapdoor"):
        return "trap"
    if b in ("ladder", "scaffolding"):
        return "ladder"
    if mod:
        if any(k in b for k in ("_log", "_wood", "_planks", "ore", "_block", "stone", "brick", "tile")):
            return "full"
        if any(k in b for k in ("table", "chest", "crystal", "waystone", "barrel", "crate", "cabinet", "shelf", "counter",
                                "chair")):
            return "nonfull"
        return "air"
    if (b.endswith("_carpet") or b in ("flower_pot", "cake", "sea_pickle", "turtle_egg", "frogspawn", "lily_pad",
                                       "repeater", "comparator", "daylight_detector", "candle")
            or b.startswith("potted_") or b.endswith(("_candle", "candle_cake", "_head", "_skull"))):
        return "small"
    if b == "snow":
        layers = int(p.get("layers", "1")) if str(p.get("layers", "1")).isdigit() else 1
        return "small" if layers <= 2 else ("low" if layers <= 5 else "full")
    if b.endswith("lantern") and b not in ("sea_lantern", "jack_o_lantern"):
        return "obst" if p.get("hanging") == "true" else "small"
    if b.endswith(("_sign", "_banner", "_button", "_pressure_plate", "torch", "rail", "_sapling", "_tulip", "_coral",
                   "_coral_fan")) or b in PLANTS:
        return "air"
    if b.endswith("_slab"):
        t = p.get("type", "bottom")
        return "slab_b" if t == "bottom" else ("slab_t" if t == "top" else "full")
    if b.endswith("_stairs"):
        return "stair_t" if p.get("half") == "top" else "stair_b"
    if (b.endswith(("_fence", "_wall", "_pane", "_bars")) or b in (
            "glass_pane", "iron_bars", "chain", "iron_chain", "bell", "end_rod", "lightning_rod", "bamboo",
            "pointed_dripstone", "brewing_stand", "grindstone", "cactus")):
        return "obst"
    if b.endswith("_bed") or b in ("campfire", "soul_campfire", "stonecutter"):
        return "low"
    if b.endswith("glass") or b in ("ice", "slime_block", "honey_block", "barrier", "spawner", "beacon", "mangrove_roots"):
        return "glassy"
    if ("chest" in b or b in ("lectern", "enchanting_table", "cauldron", "water_cauldron", "lava_cauldron",
                              "powder_snow_cauldron", "anvil", "chipped_anvil", "damaged_anvil", "composter",
                              "decorated_pot", "conduit", "hopper", "end_portal_frame", "heavy_core", "dragon_egg",
                              "big_dripleaf", "azalea", "flowering_azalea", "chorus_plant", "chorus_flower")):
        return "nonfull"
    if b in ("farmland", "dirt_path", "magma_block", "bedrock", "soul_sand", "glowstone", "sea_lantern", "shroomlight",
             "jack_o_lantern") or b.endswith("froglight"):
        return "nospawn"
    return "full"


# kind -> (passable, small, collides, top: 0 none / 1 half / 2 full / 3 fence-high / 4 stair, mobs spawn on it,
#          stops light, roof cover)
_KP = {"empty": (1, 0, 0, 0, 0, 0, 0), "air": (1, 0, 0, 0, 0, 0, 0), "small": (1, 1, 0, 0, 0, 0, 0),
       "liq": (0, 0, 0, 0, 0, 0, 0), "leaves": (0, 0, 1, 2, 0, 0, 0), "door": (1, 0, 0, 0, 0, 0, 0),
       "trap": (1, 1, 0, 0, 0, 0, 1), "ladder": (1, 0, 0, 0, 0, 0, 0), "full": (0, 0, 1, 2, 1, 1, 1),
       "glassy": (0, 0, 1, 2, 0, 0, 1), "nospawn": (0, 0, 1, 2, 0, 1, 1), "nonfull": (0, 0, 1, 2, 0, 0, 1),
       "slab_b": (0, 0, 1, 1, 0, 0, 1), "slab_t": (0, 0, 1, 2, 1, 0, 1), "stair_b": (0, 0, 1, 4, 0, 0, 1),
       "stair_t": (0, 0, 1, 2, 1, 0, 1), "obst": (0, 0, 1, 3, 0, 0, 1), "low": (0, 0, 1, 1, 0, 0, 1)}


def _emission(b, p):
    if b == "light":
        lv = str(p.get("level", "15"))
        return int(lv) if lv.isdigit() else 15
    lit = p.get("lit")
    if b in ("campfire", "soul_campfire"):
        return 0 if lit == "false" else (15 if b == "campfire" else 10)
    if b == "redstone_lamp" or b.endswith("copper_bulb"):
        if lit != "true":
            return 0
        return 15 if b in ("redstone_lamp", "copper_bulb", "waxed_copper_bulb") else 12 if "exposed" in b else 8 if "weathered" in b else 4
    if b in ("furnace", "smoker", "blast_furnace"):
        return 13 if lit == "true" else 0
    if b in ("redstone_torch", "redstone_wall_torch"):
        return 7 if p.get("lit", "true") == "true" else 0
    if b.endswith("candle_cake"):
        return 3 if lit == "true" else 0
    if b == "candle" or b.endswith("_candle"):
        c = str(p.get("candles", "1"))
        return 3 * (int(c) if c.isdigit() else 1) if lit == "true" else 0
    if b == "sea_pickle":
        c = str(p.get("pickles", "1"))
        return (3 + 3 * (int(c) if c.isdigit() else 1)) if p.get("waterlogged") == "true" else 0
    if b in ("cave_vines", "cave_vines_plant"):
        return 14 if p.get("berries") == "true" else 0
    if b == "respawn_anchor":
        c = str(p.get("charges", "0"))
        return [0, 3, 7, 11, 15][min(4, int(c))] if c.isdigit() else 0
    return LUM.get(b, 0)


class _Cls:
    __slots__ = ("pas", "floor", "lo", "hi", "spawn", "opaque", "faces", "emit", "door", "facing", "ladder", "land",
                 "bcover", "cover", "nospawnin", "struct", "garden", "coll", "leaves", "liquid", "feature", "step",
                 "name")


_CLS = {}


def _cls(state):
    k = _CLS.get(state)
    if k is not None:
        return k
    n, p = checks.name(state), checks.props(state)
    b = n.split(":")[-1]
    kd = _kind(n, p)
    pas, small, coll, top, spawn, opaque, cover = _KP[kd]
    k = _Cls()
    k.name = b
    k.pas = bool(pas)
    k.floor = top in (1, 2, 4)
    f = DIR_OF.get(p.get("facing", "north"), NORTH)
    k.facing = f
    if top == 4:
        lo, hi = [1, 1, 1, 1], [2, 2, 2, 2]
        lo[f] = hi[f] = 2
        lo[OPP[f]] = hi[OPP[f]] = 1
        k.lo, k.hi = tuple(lo), tuple(hi)
    elif top in (1, 2):
        k.lo = k.hi = (top,) * 4
    else:
        k.lo = k.hi = (0,) * 4
    k.spawn = bool(spawn)
    k.opaque = bool(opaque)
    faces = 0
    if kd in ("slab_b", "stair_b"):
        faces |= 1 << DOWN
    if kd in ("slab_t", "stair_t"):
        faces |= 1 << UP
    if kd in ("stair_b", "stair_t"):
        faces |= 1 << f
    k.faces = faces
    k.emit = 0 if ":" in n else _emission(b, p)
    k.door = kd == "door" and p.get("half", "lower") == "lower"
    k.ladder = kd == "ladder"
    k.leaves = kd == "leaves"
    k.liquid = kd == "liq"
    k.land = b in LAND or (":" not in n and b.endswith("_ore")) or (":" in n and ("ore" in b or "_log" in b))
    k.cover = bool(cover) and not k.leaves
    k.bcover = k.cover and not k.land
    k.nospawnin = bool(small) or kd in ("door", "trap", "ladder", "liq") or b.endswith("fence_gate") or "rail" in b
    k.struct = kd in ("full", "slab_b", "slab_t", "stair_b", "stair_t", "glassy", "nospawn", "leaves") and b not in FURNITURE
    k.garden = b in GARDEN
    k.coll = bool(coll)
    k.step = kd in ("slab_b", "stair_b")
    k.feature = any(t in b for t in FEATURE_PARTS) or k.emit > 0
    if len(_CLS) > 50000:
        _CLS.clear()
    _CLS[state] = k
    return k


_AIR = _cls("minecraft:air")


def _fmt(p):
    return f"({p[0]}, {p[1]}, {p[2]})"


class _Build:
    """The walk graph of a whole build: standing spots, which of them join, which are covered, the ground."""

    def __init__(self, C, ground):
        self.C = C
        get = C.get
        bmax, cmax = {}, {}
        self.emitters, self.doors = [], []
        node_at = {}
        nodes = []                           # [x, y, z, lo, hi, ceiling y (y+3 or y+4 = enough), struct, spawn]
        ymin = None
        xs0 = zs0 = 10 ** 9
        xs1 = zs1 = -10 ** 9
        lad = []
        cache = _CLS
        for (x, y, z), s in C.items():
            k = cache.get(s) or _cls(s)
            if ymin is None or y < ymin:
                ymin = y
            if x < xs0:
                xs0 = x
            if x > xs1:
                xs1 = x
            if z < zs0:
                zs0 = z
            if z > zs1:
                zs1 = z
            if k.pas:
                if k.emit:
                    self.emitters.append((x, y, z, k.emit))
                if k.door:
                    self.doors.append((x, y, z, k.facing))
                elif k.ladder:
                    lad.append((x, y, z))
                continue
            if k.emit:
                self.emitters.append((x, y, z, k.emit))
            if k.cover:
                if y > cmax.get((x, z), -10 ** 9):
                    cmax[(x, z)] = y
                if k.bcover and y > bmax.get((x, z), -10 ** 9):
                    bmax[(x, z)] = y
            if not k.floor:
                continue
            s1 = get((x, y + 1, z))
            if s1 is not None and not (cache.get(s1) or _cls(s1)).pas:
                continue
            s2 = get((x, y + 2, z))
            if s2 is not None and not (cache.get(s2) or _cls(s2)).pas:
                continue
            s3 = get((x, y + 3, z))
            ct = y + 3 if s3 is not None and not (cache.get(s3) or _cls(s3)).pas else y + 4
            node_at[(x, y, z)] = len(nodes)
            nodes.append((x, y, z, k.lo, k.hi, ct, k.struct, k.spawn and not (s1 is not None and (cache.get(s1) or _cls(s1)).nospawnin)
                          and not (s2 is not None and (cache.get(s2) or _cls(s2)).nospawnin)))
        self.ymin = ymin if ymin is not None else 0
        # ladders: a climbing spot at every ladder cell (any standing height from its floor y-1 up to y)
        for (x, y, z) in lad:
            if not self.passable(x, y + 1, z) and not self.passable(x, y - 1, z):
                continue
            ct = y + 2 if not self.passable(x, y + 1, z) else (y + 3 if not self.passable(x, y + 2, z) else y + 4)
            i = node_at.get((x, y - 1, z))
            rec = (x, y - 1, z, (0, 0, 0, 0), (2, 2, 2, 2), ct, False, False)
            if i is None:
                node_at[(x, y - 1, z)] = len(nodes)
                nodes.append(rec)
            else:
                nodes[i] = rec
        # a build without terrain stands on its lowest layer: empty cells of that layer are level ground
        if ground is None and C:
            ym = self.ymin
            for x in range(xs0 - 2, xs1 + 3):
                for z in range(zs0 - 2, zs1 + 3):
                    if (x, ym, z) in node_at:
                        continue
                    s0 = get((x, ym, z))
                    if s0 is not None and (cache.get(s0) or _cls(s0)).name not in EMPTY:
                        continue
                    if not (self.passable(x, ym + 1, z) and self.passable(x, ym + 2, z)):
                        continue
                    ct = ym + 3 if not self.passable(x, ym + 3, z) else ym + 4
                    node_at[(x, ym, z)] = len(nodes)
                    nodes.append((x, ym, z, (2, 2, 2, 2), (2, 2, 2, 2), ct, True, False))
        self.nodes, self.node_at, self.bmax, self.cmax = nodes, node_at, bmax, cmax
        by_col = collections.defaultdict(list)
        for i, n in enumerate(nodes):
            by_col[(n[0], n[2])].append(i)
        self.by_col = by_col
        # walk links (no jump: the standing height changes by at most half a block; 1.8 headroom over the higher one)
        parent = list(range(len(nodes)))
        self.parent = parent

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        self.find = find
        lad_set = self.lad_set = set(lad)
        for i, (x, y, z, lo, hi, ct, _s, _p) in enumerate(nodes):
            for d in (EAST, SOUTH):
                dx, dz = DXZ[d]
                for dy in (-1, 0, 1):
                    j = node_at.get((x + dx, y + dy, z + dz))
                    if j is None:
                        continue
                    if self._link(nodes[i], nodes[j], d):
                        a, b = find(i), find(j)
                        if a != b:
                            parent[a] = b
            if (x, y + 1, z) in lad_set:                                    # climbing up a ladder
                j = node_at.get((x, y + 1, z))
                if j is not None:
                    a, b = find(i), find(j)
                    if a != b:
                        parent[a] = b
        self.root = [find(i) for i in range(len(nodes))]
        # the ground: standing spots under the open sky (nothing but leaves above them); the outside = the walk areas
        # with a lot of it (streets, yards, the land), not a balcony or a small roof terrace
        gcount = collections.Counter()
        for i, (x, y, z, *_r) in enumerate(nodes):
            if cmax.get((x, z), -10 ** 9) <= y + 2:
                gcount[self.root[i]] += 1
        top = max(gcount.values()) if gcount else 0
        self.outside = {r for r, c in gcount.items() if c >= max(16, top // 10)} or ({max(gcount, key=gcount.get)} if gcount else set())

    @staticmethod
    def _link(a, b, d):
        ya, yb = a[1], b[1]
        loa, hia = 2 * ya + a[3][d], 2 * ya + a[4][d]
        o = OPP[d]
        lob, hib = 2 * yb + b[3][o], 2 * yb + b[4][o]
        if max(0, lob - hia, loa - hib) > 1:
            return False
        hc = max(loa, lob) + 3.6
        return 2 * a[5] >= hc and 2 * b[5] >= hc

    def state(self, x, y, z):
        s = self.C.get((x, y, z))
        return _AIR if s is None else (_CLS.get(s) or _cls(s))

    def passable(self, x, y, z):
        s = self.C.get((x, y, z))
        return s is None or (_CLS.get(s) or _cls(s)).pas

    def covered(self, x, z, y):
        """A building block above the standing spot on floor y (higher than its 2 free blocks)."""
        return self.bmax.get((x, z), -10 ** 9) > y + 2

    def reached(self, i):
        return self.root[i] in self.outside


def _rooms(B):
    """Rooms: covered standing spots joined side by side (not through a door or a 1-wide gap in a wall) that the open
    air reaches only through a few cells: walls all round. Each room also takes the doorway spots next to it.
    Returns a list of node index lists."""
    nodes, node_at = B.nodes, B.node_at
    bmax = B.bmax
    st = B.state
    cov, gap = set(), set()
    for i, (x, y, z, *_r) in enumerate(nodes):
        if bmax.get((x, z), -10 ** 9) <= y + 2:
            continue
        cov.add(i)
        fy = y + 1
        if st(x, fy, z).door:
            gap.add(i)
            continue
        if ((x + 1, y, z) in node_at or (x - 1, y, z) in node_at) and ((x, y, z + 1) in node_at or (x, y, z - 1) in node_at):
            continue                                                # open on one side along x and along z: no gap
        side = []
        for dx, dz in DXZ:
            k1, k2 = st(x + dx, fy, z + dz), st(x + dx, fy + 1, z + dz)
            side.append(not k1.pas or not k2.pas or k1.door)
        if (side[0] and side[1]) or (side[2] and side[3]):
            gap.add(i)                                              # between two wall blocks: a doorway or a passage
    seen, rooms = set(), []
    for i0 in cov:
        if i0 in seen or i0 in gap:
            continue
        seen.add(i0)
        comp, k, leaks, walls, doorways = [i0], 0, 0, 0, set()
        while k < len(comp):
            x, y, z = nodes[comp[k]][:3]
            k += 1
            fy = y + 1
            for dx, dz in DXZ:
                qx, qz = x + dx, z + dz
                j = node_at.get((qx, y, qz))
                if j is None:
                    for dy in (-1, 1, -2, 2):
                        j = node_at.get((qx, y + dy, qz))
                        if j is not None:
                            break
                if j is not None and j in cov:
                    if j in gap:
                        doorways.add(j)
                    elif j not in seen:
                        seen.add(j)
                        comp.append(j)
                    continue
                side = _side(B, x, fy, z, dx, dz)
                if side == "wall":
                    walls += 1
                elif side == "leak":
                    leaks += 1                                      # open air, a drop or a spot under the sky
        tall = sum(1 for i in comp if nodes[i][5] >= nodes[i][1] + 4)
        if leaks <= max(2, (walls + leaks) * 15 // 100) and tall * 2 >= len(comp):
            rooms.append(comp + sorted(doorways))                   # walls all round, mostly 3 free blocks high
    return rooms


def _side(B, x, fy, z, dx, dz):
    """Looking out from the spot with its feet at fy: 'wall' (feet and head height closed, or a door, within 3 blocks,
    behind any railing, furniture or low beam on the way), 'leak' (the open sky is reached first: a railing or the beam
    round a stilt deck has open air behind it) or 'in' (more covered floor: the building goes on)."""
    st = B.state
    for k in range(1, 4):
        cx, cz = x + dx * k, z + dz * k
        k1, k2 = st(cx, fy, cz), st(cx, fy + 1, cz)
        if k1.door or (not k1.pas and not k2.pas):
            return "wall"
        if B.bmax.get((cx, cz), -10 ** 9) <= fy + 1:
            return "leak"                                           # under the open sky
    return "in"


def _buildings(B, rooms):
    """Rooms stacked over each other (sharing a column) are one building; only buildings people use are kept."""
    rooms = [r for r in rooms if _has_square(B, r)]             # a nook, a planter box or a closet is no room
    parent = list(range(len(rooms)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    owner = {}
    for r, comp in enumerate(rooms):
        for i in comp:
            c = B.nodes[i][0], B.nodes[i][2]
            o = owner.get(c)
            if o is None:
                owner[c] = r
            else:
                a, b = find(o), find(r)
                if a != b:
                    parent[a] = b
    groups = collections.defaultdict(list)
    for r, comp in enumerate(rooms):
        groups[find(r)].extend(comp)
    out = []
    for comp in groups.values():
        if len(comp) < MIN_ROOM:
            continue
        if _used(B, comp):
            out.append(sorted(comp, key=lambda i: (B.nodes[i][1], B.nodes[i][0], B.nodes[i][2])))
    return out


def _has_square(B, comp):
    """A 3 x 3 patch of floor on one level: a room, not a bay between posts, a corridor or the gap behind a wall."""
    cells = {B.nodes[i][:3] for i in comp}
    return any(all((x + a, y, z + c) in cells for a in range(3) for c in range(3)) for (x, y, z) in cells)


def _used(B, comp):
    """Something a house has: a door, window, bed, furniture or light at or next to its floor, or a way in on foot."""
    st = B.state
    for i in comp:
        if B.reached(i):
            return True
        x, y, z = B.nodes[i][:3]
        for yy in (y + 1, y + 2):
            if st(x, yy, z).feature:
                return True
            for dx, dz in DXZ:
                if st(x + dx, yy, z + dz).feature:
                    return True
    return False


class _Light:
    """Block light in the boxes of the buildings (+ margin), spread from every light source there. Worked out on a flat
    byte grid (one cell per block of the boxes' bounding box, padded by 1 so no step leaves it)."""

    def __init__(self, B, buildings):
        boxes = []
        for comp in buildings:
            xs = [B.nodes[i][0] for i in comp]
            zs = [B.nodes[i][2] for i in comp]
            ys = [B.nodes[i][1] for i in comp]
            boxes.append((min(xs) - LIGHT_MARGIN, max(xs) + LIGHT_MARGIN, min(ys) - 2, max(ys) + 8,
                          min(zs) - LIGHT_MARGIN, max(zs) + LIGHT_MARGIN))
        X0 = min(b[0] for b in boxes) - 1
        Y0 = min(b[2] for b in boxes) - 1
        Z0 = min(b[4] for b in boxes) - 1
        H = max(b[3] for b in boxes) + 2 - Y0
        L = max(b[5] for b in boxes) + 2 - Z0
        W = max(b[1] for b in boxes) + 2 - X0
        SX, SY = H * L, L
        self.o, self.SX, self.SY, self.dim = (X0, Y0, Z0), SX, SY, (W, H, L)
        inside = bytearray(W * H * L)                       # 1 = in a building's box
        for (x0, x1, y0, y1, z0, z1) in boxes:
            run = b"\x01" * (z1 - z0 + 1)
            for x in range(x0, x1 + 1):
                base = (x - X0) * SX + (z0 - Z0)
                for y in range(y0, y1 + 1):
                    i = base + (y - Y0) * SY
                    inside[i:i + len(run)] = run
        lvl = bytearray(W * H * L)
        kind = bytearray(W * H * L)                         # 0 not looked at, 1 + faces * 2 = light passes, 255 = stops it
        buckets = [[] for _ in range(16)]
        for (x, y, z, e) in B.emitters:
            if X0 < x < X0 + W - 1 and Y0 < y < Y0 + H - 1 and Z0 < z < Z0 + L - 1:
                i = (x - X0) * SX + (y - Y0) * SY + (z - Z0)
                if inside[i] and e > lvl[i]:
                    lvl[i] = e
                    buckets[e].append(i)
        get = B.C.get
        steps = ((SX, EAST), (-SX, WEST), (1, SOUTH), (-1, NORTH), (SY, UP), (-SY, DOWN))

        def look(i):
            x, r = divmod(i, SX)
            y, z = divmod(r, SY)
            t = get((x + X0, y + Y0, z + Z0))
            if t is None:
                k = 1
            else:
                kt = _CLS.get(t) or _cls(t)
                k = 255 if kt.opaque else 1 + 2 * kt.faces
            kind[i] = k
            return k
        for lv in range(15, 1, -1):
            nxt = buckets[lv - 1]
            for i in buckets[lv]:
                if lvl[i] != lv:
                    continue
                k0 = kind[i] or look(i)
                fa = 0 if k0 == 255 else (k0 - 1) >> 1               # a light source that is a full block shines out
                for off, d in steps:
                    if fa >> d & 1:
                        continue
                    n = i + off
                    if lvl[n] >= lv - 1 or not inside[n]:
                        continue
                    k = kind[n] or look(n)
                    if k == 255 or ((k - 1) >> 1) >> OPP[d] & 1:
                        continue
                    lvl[n] = lv - 1
                    nxt.append(n)
        self.lvl = lvl

    def at(self, x, y, z):
        X0, Y0, Z0 = self.o
        W, H, L = self.dim
        if not (X0 <= x < X0 + W and Y0 <= y < Y0 + H and Z0 <= z < Z0 + L):
            return 0
        return self.lvl[(x - X0) * self.SX + (y - Y0) * self.SY + (z - Z0)]


def _where(B, comp):
    xs = [B.nodes[i][0] for i in comp]
    zs = [B.nodes[i][2] for i in comp]
    ys = [B.nodes[i][1] for i in comp]
    return f"the building at x {min(xs)}..{max(xs)}, z {min(zs)}..{max(zs)} (floor y {min(ys)})"


def _clusters(B, idxs):
    """Groups of standing spots joined side by side on the same floor height."""
    left = set(idxs)
    out = []
    while left:
        i = left.pop()
        comp, k = [i], 0
        while k < len(comp):
            x, y, z = B.nodes[comp[k]][:3]
            k += 1
            for dx, dz in DXZ:
                j = B.node_at.get((x + dx, y, z + dz))
                if j is not None and j in left:
                    left.remove(j)
                    comp.append(j)
        out.append(comp)
    return out


def _centre(B, comp):
    xs = sorted(B.nodes[i][0] for i in comp)
    zs = sorted(B.nodes[i][2] for i in comp)
    cx, cz = xs[len(xs) // 2], zs[len(zs) // 2]
    return min(comp, key=lambda i: (abs(B.nodes[i][0] - cx) + abs(B.nodes[i][2] - cz), B.nodes[i][1]))


def _door_text(B, comp, cols):
    """Why no door of this building joins the ground, with the fix, and the spot to name."""
    nodes = B.nodes
    ys = [nodes[i][1] for i in comp]
    near = set()
    for (x, z) in cols:
        near.add((x, z))
        for dx, dz in DXZ:
            near.add((x + dx, z + dz))
    lo, hi = min(ys), max(ys) + 2
    doors = [d for d in B.doors if (d[0], d[2]) in near and lo <= d[1] <= hi]
    doors.sort(key=lambda d: d[1])
    for (x, y, z, f) in doors:
        ax = (0, 1) if f in (SOUTH, NORTH) else (1, 0)             # the door's two sides
        sides = [(x - ax[0], z - ax[1]), (x + ax[0], z + ax[1])]
        outs = [c for c in sides if c not in cols]
        if not outs:
            continue                                               # a door between two rooms
        ox, oz = outs[-1] if len(outs) == 2 and (x, z) not in cols and sides[0] in cols else outs[0]
        walk_in = DIR_NAME[DXZ.index((x - ox, z - oz))]
        st = B.state
        k1, k2 = st(ox, y, oz), st(ox, y + 1, oz)
        if not k1.pas or not k2.pas:
            what = (k1 if not k1.pas else k2).name
            return (x, y, z), (f"its door at {_fmt((x, y, z))} opens onto {what} at {_fmt((ox, y if not k1.pas else y + 1, oz))}: "
                               f"clear the 2 blocks in front of the door and give them a floor at the door's level")
        if B.node_at.get((ox, y - 1, oz)) is not None:
            return (x, y, z), (f"the floor in front of its door at {_fmt((ox, y - 1, oz))} does not join the ground "
                               f"around it without a jump: lay a path from the door to the ground, every 1-block rise a "
                               f"bottom stair (straight_stair_run, porch(..., steps=n))")
        drop = 0
        yy = y - 1
        while drop < 12 and yy >= B.ymin and B.passable(ox, yy, oz):
            drop += 1
            yy -= 1
        if drop == 0:
            return (x, y, z), (f"in front of its door at {_fmt((x, y, z))} is {st(ox, y - 1, oz).name} at "
                               f"{_fmt((ox, y - 1, oz))}, nothing to walk on: put a floor block or a path there at the door's level")
        if drop == 1:
            return (x, y, z), (f"its door at {_fmt((x, y, z))} is 1 block above the ground in front of it: put a bottom "
                               f"stair facing {walk_in} at {_fmt((ox, y - 1, oz))} as a step (or porch(..., steps=1)), "
                               f"or lower the floor to the ground")
        return (x, y, z), (f"its door at {_fmt((x, y, z))} opens onto a drop of {drop} block{'s' if drop != 1 else ''}: "
                           f"build steps down to the ground (porch(..., steps={drop}) or straight_stair_run, every rise a "
                           f"bottom stair) or move the door down to the ground floor")
    i = _centre(B, [j for j in comp if nodes[j][1] == lo] or comp)
    x, y, z = nodes[i][:3]
    return (x, y + 1, z), ("it has no door or 2-high opening at the level of the ground outside: put a door in an outside "
                           "wall of the ground floor (doorway(...)), with the floor inside and the ground in front at the "
                           "door's level or one stair step lower")


def _gap_reason(B, a, b):
    """Why spot b (not reached) cannot be walked to from its reached neighbour a."""
    xa, ya, za = B.nodes[a][:3]
    xb, yb, zb = B.nodes[b][:3]
    d = DXZ.index((xb - xa, zb - za))
    ha = 2 * ya + B.nodes[a][4][d]
    hb = 2 * yb + B.nodes[b][3][OPP[d]]
    if hb - ha > 1:
        rise = (hb - ha) / 2
        return (f"{_fmt((xb, yb, zb))} is a {rise:g}-block step up from {_fmt((xa, ya, za))}: make the rise a bottom stair "
                f"or a slab step, or keep one floor level per storey")
    if ha - hb > 1:
        return (f"{_fmt((xb, yb, zb))} is {(ha - hb) / 2:g} blocks lower than {_fmt((xa, ya, za))} and there is no way "
                f"back up: put a stair there")
    return (f"the step from {_fmt((xa, ya, za))} to {_fmt((xb, yb, zb))} has no room for the head (1.8 blocks over the "
            f"higher one; a step up right inside a 2-high door or under a beam): put a flat floor cell before the step, "
            f"or raise the ceiling or opening there")


def _post_near(B, x, z, base, r=4):
    """A post or pillar within r blocks that runs down from under the floor at `base` to the ground (land, water or
    the build's lowest layer): the floor there stands on stilts, it does not hang."""
    for px in range(x - r, x + r + 1):
        for pz in range(z - r, z + r + 1):
            yy = base - 1
            if not B.state(px, yy, pz).coll:
                continue
            while yy >= B.ymin:
                k = B.state(px, yy, pz)
                if k.land or k.liquid:
                    return True
                if not k.coll:
                    break
                yy -= 1
            else:
                return True
    return False


def findings(C, ground=None):
    """The house findings of a build: [(check, (x, y, z), text)]."""
    if not C:
        return []
    B = _Build(C, ground)
    rooms = _rooms(B)
    if not rooms:
        return []
    blds = _buildings(B, rooms)
    if not blds:
        return []
    light = _Light(B, blds)
    out = []
    holes_seen = set()
    for comp in blds:
        out += _one(B, comp, light, holes_seen)
    return out


def _one(B, comp, light, holes_seen):
    nodes = B.nodes
    out = []
    where = _where(B, comp)
    cset = set(comp)
    cols = {(nodes[i][0], nodes[i][2]) for i in comp}
    reached = [i for i in comp if B.reached(i)]
    door_ok = bool(reached)
    lv_all = collections.Counter(nodes[i][1] for i in comp)
    storeys = sorted(y for y, c in lv_all.items() if c >= 3) or sorted(lv_all)
    if not door_ok:
        at, why = _door_text(B, comp, cols)
        out.append(("door_unreachable", at, f"Nobody can walk into {where} from the ground: {why}"))
        ground_roots = {B.root[i] for i in comp if nodes[i][1] == storeys[0]}       # judge the rest from the ground floor
        entry = [i for i in comp if B.root[i] in ground_roots]
    else:
        entry = reached
    eset = set(entry)
    # ---- INTERIOR: the storeys the walker reaches; spots up to 2 above/below them belong to the storey
    lvc = collections.Counter(nodes[i][1] for i in entry)
    need = max(4, len(entry) * 15 // 100)
    main = sorted(y for y, c in lvc.items() if c >= need) or sorted(lvc)
    den = [i for i in comp if nodes[i][1] in main or (nodes[i][6] and any(abs(nodes[i][1] - m) <= 2 for m in main))]
    off = [i for i in den if i not in eset and nodes[i][1] not in main]
    drop = set()
    for cl in _clusters(B, off):
        if len(cl) < 9:
            drop.update(cl)                                     # a table, bench or furniture top is no floor
    den = [i for i in den if i not in drop]
    num = sum(1 for i in den if i in eset)
    if den and num * 100 < MAIN_PCT * len(den):
        pct = 100 * num // len(den)
        miss = [i for i in den if i not in eset]
        dset = set(den)
        reason, at, best = None, nodes[miss[0]][:3], 3
        for a in entry:                                         # the edge of the reached floor: why it stops there
            x, y, z = nodes[a][:3]
            for dx, dz in DXZ:
                for dy in (-2, -1, 0, 1, 2):
                    b = B.node_at.get((x + dx, y + dy, z + dz))
                    if b is None or b in eset or b not in cset:
                        continue
                    rank = 0 if b in dset else 1
                    if rank < best:
                        best, reason, at = rank, _gap_reason(B, a, b), nodes[b][:3]
                if best == 0:
                    break
            if best == 0:
                break
        reason = reason or f"{_fmt(at)} is walled off from the rest: open a doorway (2 high) to it"
        out.append(("interior_unreachable", at,
                    f"Only {pct}% of the floor inside {where} can be walked to from the way in ({num} of {len(den)} "
                    f"cells): {reason}"))
    # ---- LOW HEADROOM: 1-high spots next to the floor people walk on (any reached spot in the building: rooms,
    # stairs, ladders)
    roots = {B.root[i] for i in entry}
    walkers = entry + [j for c in cols for j in B.by_col.get(c, ()) if j not in eset and B.root[j] in roots
                       and (B.state(*nodes[j][:3]).step or (nodes[j][0], nodes[j][1] + 1, nodes[j][2]) in B.lad_set)]
    low = set()
    for i in walkers:
        x, y, z = nodes[i][:3]
        for dx, dz in DXZ:
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy, z + dz)
                if q in B.node_at or (q[0], q[2]) not in cols:
                    continue
                if not B.state(*q).struct or not B.passable(q[0], q[1] + 1, q[2]) or B.passable(q[0], q[1] + 2, q[2]):
                    continue                                    # a floor (not a campfire or furniture top), 1 high
                under = B.state(q[0], q[1] - 1, q[2])
                if under.coll and not under.floor:
                    continue                                    # a table top on a fence post or a wall
                if not B.covered(q[0], q[2], q[1] - 1):
                    continue
                if any(B.state(q[0], q[1] + h, q[2]).step and B.node_at.get((q[0], q[1] + h, q[2])) is not None
                       and B.root[B.node_at[(q[0], q[1] + h, q[2])]] in roots for h in (2, 3, 4)):
                    continue                                    # the nook under a stair people walk on
                low.add(q)
    if len(low) >= 2:
        ex = sorted(low, key=lambda p: (p[1], p[0], p[2]))
        out.append(("low_headroom", ex[0],
                    f"{len(low)} floor spots inside {where} that people walk up to have only 1 block of headroom, e.g. "
                    + ", ".join(_fmt(p) for p in ex[:3])
                    + ": raise the ceiling or roof over them to 3 free blocks (2 at least), or move what hangs at head "
                      "height"))
    # ---- LIT / NO SPAWN on the reached floor inside
    dark = [i for i in entry if nodes[i][7] and light.at(nodes[i][0], nodes[i][1] + 1, nodes[i][2]) == 0]
    for cl in sorted(_clusters(B, dark), key=len, reverse=True):
        c = _centre(B, cl)
        x, y, z = nodes[c][:3]
        ct = y + 1
        while ct < y + 12 and B.passable(x, ct, z):
            ct += 1
        tip = (f"hang a lantern from the ceiling at {_fmt((x, ct - 1, z))}" if ct - 1 >= y + 3 and ct < y + 12
               else f"put a lantern or a wall torch near {_fmt((x, y + 1, z))}")
        out.append(("dark_spawn_spot", (x, y, z),
                    f"Dark floor inside {where}: {_fmt((x, y, z))}"
                    + (f" and {len(cl) - 1} more cell{'s' if len(cl) > 2 else ''} next to it have" if len(cl) > 1 else " has")
                    + f" block light 0, so mobs can spawn there - {tip} (a light every 6 blocks or so)"))
    # ---- ROOF: small patches of floor inside with open sky above
    xs = [c[0] for c in cols]
    zs = [c[1] for c in cols]
    for ys in storeys:
        sky = set()
        for x in range(min(xs), max(xs) + 1):
            for z in range(min(zs), max(zs) + 1):
                j = B.node_at.get((x, ys, z))
                if j is not None and j not in cset and B.cmax.get((x, z), -10 ** 9) <= ys + 2:
                    sky.add((x, z))
        while sky:
            c0 = sky.pop()
            patch, k = [c0], 0
            while k < len(patch):
                x, z = patch[k]
                k += 1
                for dx, dz in DXZ:
                    q = (x + dx, z + dz)
                    if q in sky:
                        sky.remove(q)
                        patch.append(q)
            pset = set(patch)
            ring = {(x + dx, z + dz) for (x, z) in patch for dx, dz in DXZ} - pset
            if not ring or len(patch) > 12:
                continue                                        # a courtyard, not a hole
            inside = sum(1 for (x, z) in ring if B.cmax.get((x, z), -10 ** 9) > ys + 1)
            mine = sum(1 for (x, z) in ring if any(B.node_at.get((x, yy, z)) in cset for yy in (ys - 1, ys, ys + 1)))
            if mine * 2 < len(ring) or inside * 4 < len(ring) * 3:
                continue                                        # not in a room: a roof top, a terrace, the yard
            fl = [B.state(x, ys, z) for (x, z) in patch]
            if sum(1 for k_ in fl if k_.garden or k_.step) * 2 >= len(fl):
                continue                                        # a garden bed or a roof slope
            if any(B.state(x, yy, z).leaves for (x, z) in patch for yy in range(ys + 3, ys + 20)):
                continue                                        # under a tree
            if any(B.state(x, yy, z).ladder or B.state(x, yy, z).step for (x, z) in patch for yy in range(ys + 1, ys + 12)):
                continue                                        # a ladder hatch or a stairwell up to the roof
            key = (ys, min(patch))
            if key in holes_seen:
                continue
            holes_seen.add(key)
            hx, hz = min(patch)
            out.append(("roof_hole", (hx, ys, hz),
                        f"Roof hole in {where}: the sky is open over the floor at {_fmt((hx, ys, hz))}"
                        + (f" and {len(patch) - 1} more cell{'s' if len(patch) > 2 else ''} next to it" if len(patch) > 1 else "")
                        + " - close the roof over it (rain and snow fall in, and it is dark at night)"))
    # ---- GROUNDED: the ground-storey walls stand on something and are not buried
    y0 = storeys[0]
    gcols = {(nodes[i][0], nodes[i][2]) for i in comp if abs(nodes[i][1] - y0) <= 1}
    wall = set()
    for (x, z) in gcols:
        for dx, dz in DXZ:
            q = (x + dx, z + dz)
            if q in gcols:
                continue
            if not B.passable(q[0], y0 + 1, q[1]) or not B.passable(q[0], y0 + 2, q[1]) or B.state(q[0], y0 + 1, q[1]).door:
                wall.add(q)
    gaps = {}
    for (x, z) in wall:
        base = next((yy for yy in range(y0 - 1, y0 + 2) if B.state(x, yy, z).coll), None)
        if base is None:
            continue
        gap, yy = 0, base - 1
        while gap < 12 and yy >= B.ymin and not B.state(x, yy, z).coll:
            gap += 1
            yy -= 1
        gaps[(x, z)] = (base, gap)
    ok_cols = [c for c, (_b, g) in gaps.items() if g <= 1]
    hang = sorted((c for c, (b, g) in gaps.items() if g >= 2
                   and not any(abs(c[0] - o[0]) <= 2 and abs(c[1] - o[1]) <= 2 for o in ok_cols)
                   and not _post_near(B, c[0], c[1], b)),
                  key=lambda c: -gaps[c][1])
    if hang:
        hx, hz = hang[0]
        base, gap = gaps[(hx, hz)]
        out.append(("wall_over_air", (hx, base, hz),
                    f"The wall of {where} hangs {gap}{'+' if gap >= 12 else ''} blocks over air at {_fmt((hx, base, hz))}"
                    + (f" ({len(hang)} wall blocks)" if len(hang) > 1 else "")
                    + ": build the foundation down to the ground under the walls (or posts every 3 blocks), "
                      "or lower the house onto the ground"))
    buried = {}
    for (x, z) in wall:
        for dx, dz in DXZ:
            q = (x + dx, z + dz)
            if q in gcols or q in wall or q in buried:
                continue
            k0 = B.state(q[0], y0, q[1])
            if not (k0.land and k0.coll):
                continue
            t = y0
            while t < y0 + 10 and B.state(q[0], t + 1, q[1]).land and B.state(q[0], t + 1, q[1]).coll:
                t += 1
            if t - y0 >= 2:
                buried[q] = t
    if buried:
        bq = max(buried, key=lambda q: buried[q])
        t = buried[bq]
        out.append(("land_against_wall", (bq[0], t, bq[1]),
                    f"Land is piled {t - y0} blocks up the outside wall of {where} at {_fmt((bq[0], t, bq[1]))}"
                    + (f" ({len(buried)} spots)" if len(buried) > 1 else "")
                    + ": dig the ground back so it meets the wall at floor level and slopes away 1 block down per block, "
                      "or raise the house onto a foundation"))
    return out
