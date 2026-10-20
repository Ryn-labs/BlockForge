"""Makes sure every block in a build can really exist in vanilla Minecraft where it is.

`process()` fixes what it safely can (a hanging lantern on a wall gets a fence bracket, a floor torch on a wall
becomes a wall torch...) and returns what's left as problems for the AI to fix. `process(final=True)` is the last
pass: whatever still couldn't exist (it would pop off or fall the moment the world updates) is replaced or removed,
and listed."""
import re
from collections import Counter

from . import mods as modlib
from . import redstone as rs
from . import store

HORIZ, OPP, DIRS = rs.HORIZ, rs.OPP, rs.DIRS
_add, _name, _props, _with = rs._add, rs._name, rs._props, rs._with

SOIL = {"grass_block", "dirt", "coarse_dirt", "podzol", "rooted_dirt", "moss_block", "mud", "muddy_mangrove_roots", "farmland",
        "mycelium", "dirt_path"}
SAND = {"sand", "red_sand", "suspicious_sand"}
GRAVITY = {"sand": "sandstone", "red_sand": "red_sandstone", "gravel": "stone", "suspicious_sand": "sandstone",
           "suspicious_gravel": "stone", "anvil": "iron_block", "chipped_anvil": "iron_block", "damaged_anvil": "iron_block",
           "dragon_egg": "obsidian"}
TORCHES = {"torch": "wall_torch", "soul_torch": "soul_wall_torch", "redstone_torch": "redstone_wall_torch"}
WALL_TORCHES = {v: k for k, v in TORCHES.items()}
SOIL_PLANTS = re.compile(r"^(short_grass|fern|tall_grass|large_fern|dandelion|poppy|blue_orchid|allium|azure_bluet|oxeye_daisy|cornflower|"
                         r"lily_of_the_valley|wither_rose|torchflower|pitcher_plant|sunflower|lilac|rose_bush|peony|pink_petals|"
                         r"(red|orange|white|pink)_tulip|(oak|spruce|birch|jungle|acacia|dark_oak|cherry|mangrove)_sapling|"
                         r"azalea|flowering_azalea|sweet_berry_bush|bamboo_sapling|short_dry_grass|bush|firefly_bush)$")
DOUBLE = {"tall_grass", "large_fern", "sunflower", "lilac", "rose_bush", "peony", "pitcher_plant", "tall_seagrass"}
CROPS = {"wheat", "carrots", "potatoes", "beetroots", "melon_stem", "pumpkin_stem"}
WALL_MOUNT = re.compile(r"(^ladder$|_wall_sign$|_wall_hanging_sign$|_wall_banner$|^tripwire_hook$|_wall_head$|_wall_skull$|_wall_fan$|"
                        r"^cocoa$|_wall_torch$)")


def _is_fence(n):
    return bool(n) and n.endswith("_fence") and n != "nether_brick_fence"


def _solid(st):
    return rs._solid(st) or bool(st and "glass" in (_name(st) or "") and "pane" not in (_name(st) or ""))


def _hang_ok(st):
    n = _name(st)
    if not n:
        return False
    if _solid(st) or n.endswith(("_leaves", "chain", "iron_bars", "_fence", "_wall")) or "_pane" in n:
        return True
    p = _props(st)
    return (n.endswith("_stairs") and p.get("half") == "top") or (n.endswith("_slab") and p.get("type") in ("top", "double"))


def _floor_ok(st):
    return rs._can_support(st)


class Ctx:
    def __init__(self, blocks):
        self.b = blocks
        self.fixed, self.problems = [], []
        self.fixes = Counter()
        self.cnt = Counter()
        fences = Counter(_name(s) for s in blocks.values() if _is_fence(_name(s)))
        self.fence = fences.most_common(1)[0][0] if fences else "oak_fence"

    def get(self, p, d=None):
        return self.b.get(p if d is None else _add(p, d))

    def fix(self, kind, text):
        self.fixes[text] += 1

    def problem(self, kind, p, text):
        self.cnt[kind + "|n"] += 1
        if self.cnt[kind + "|n"] <= 3:
            self.problems.append(f"{text} at {p}")
        elif self.cnt[kind + "|n"] == 4:
            self.problems.append(f"...and more of the same kind ({kind})")


def _wall_dir(c, p):
    """A horizontal direction that has a solid wall block next to p, or None."""
    for d in HORIZ:
        if _solid(c.get(p, d)):
            return d
    return None


def _check_block(c, p, st, final):
    n = _name(st)
    pr = _props(st)
    b = c.b
    below, above = c.get(p, "down"), c.get(p, "up")

    # ---- leaves must not decay
    if n and n.endswith("_leaves") and pr.get("persistent") != "true":
        b[p] = _with(st, persistent="true")
        c.fix("leaves", "Made leaves persistent so they never decay")
        return

    # ---- lanterns
    if n in ("lantern", "soul_lantern"):
        hanging = pr.get("hanging") == "true"
        ok_h, ok_f = _hang_ok(above), _floor_ok(below)
        if (hanging and ok_h) or (not hanging and ok_f):
            return
        if hanging and ok_f:
            b[p] = _with(st, hanging="false"); c.fix("lantern", "Lanterns that had nothing above now stand on the block below"); return
        if not hanging and ok_h:
            b[p] = _with(st, hanging="true"); c.fix("lantern", "Lanterns that had nothing below now hang from the block above"); return
        wd = _wall_dir(c, p)
        up = _add(p, "up")
        if wd and not above:
            b[up] = f"minecraft:{c.fence}"
            b[p] = _with(st, hanging="true")
            c.fix("bracket", "Lanterns on a wall now hang from a small fence bracket (lanterns can't attach to a wall sideways in vanilla)")
            return
        if final:
            del b[p]; c.fix("removed", "Removed lanterns with nothing to hang from or stand on")
        else:
            c.problem("lantern", p, f"{n} has nothing to hang from or stand on")
        return

    # ---- torches
    if n in TORCHES:
        if _floor_ok(below):
            return
        wd = _wall_dir(c, p)
        if wd:
            b[p] = f"minecraft:{TORCHES[n]}[facing={OPP[wd]}]"
            c.fix("torch", "Floor torches with no floor below became wall torches on the wall next to them")
        elif final:
            del b[p]; c.fix("removed", "Removed torches with nothing to attach to")
        else:
            c.problem("torch", p, f"{n} has no floor or wall to attach to")
        return
    if n in WALL_TORCHES:
        f = pr.get("facing", "north")
        if _solid(c.get(p, OPP[f])):
            return
        wd = _wall_dir(c, p)
        if wd:
            b[p] = _with(st, facing=OPP[wd]); c.fix("torch", "Wall torches that weren't touching a wall were turned to face one")
        elif _floor_ok(below):
            b[p] = f"minecraft:{WALL_TORCHES[n]}"; c.fix("torch", "Wall torches next to nothing now stand on the floor")
        elif final:
            del b[p]; c.fix("removed", "Removed torches with nothing to attach to")
        else:
            c.problem("torch", p, f"{n} isn't attached to anything")
        return

    # ---- things mounted on a wall (ladders, wall signs, banners...)
    if n and WALL_MOUNT.search(n) and not n.endswith("_wall_torch"):
        f = pr.get("facing", "north")
        if _solid(c.get(p, OPP[f])):
            return
        wd = _wall_dir(c, p)
        if wd:
            b[p] = _with(st, facing=OPP[wd]); c.fix("mount", "Wall-mounted blocks (ladders, signs, banners) that weren't touching a wall were turned to face one")
        elif final:
            del b[p]; c.fix("removed", "Removed wall-mounted blocks with no wall behind them")
        else:
            c.problem("mount", p, f"{n} has no wall behind it")
        return

    # ---- buttons / levers by face
    if n and (n == "lever" or n.endswith("_button")):
        face, f = pr.get("face", "wall"), pr.get("facing", "north")
        back = {"floor": c.get(p, "down"), "ceiling": c.get(p, "up"), "wall": c.get(p, OPP[f])}.get(face)
        if _solid(back):
            return
        wd = _wall_dir(c, p)
        if wd:
            b[p] = _with(st, face="wall", facing=OPP[wd]); c.fix("mount", "Buttons/levers floating in the air were attached to a nearby wall")
        elif final:
            del b[p]; c.fix("removed", "Removed buttons/levers with nothing to attach to")
        else:
            c.problem("mount", p, f"{n} isn't attached to anything")
        return

    # ---- doors and double plants: both halves
    if n and (n.endswith("_door") or n in DOUBLE):
        half = pr.get("half")
        if half == "lower":
            if not (_name(above) == n and _props(above).get("half") == "upper"):
                if not above:
                    b[_add(p, "up")] = _with(st, half="upper"); c.fix("halves", "Added the missing top half of doors and tall plants")
                else:
                    del b[p]; c.fix("removed", "Removed doors/tall plants with something blocking their top half")
                return
            if n.endswith("_door") and not _floor_ok(below):
                c.problem("door", p, f"{n} has nothing solid under it")
            elif n in DOUBLE and _name(below) not in SOIL and n != "tall_seagrass":
                _soil_problem(c, p, n, final, double=True)
        elif half == "upper":
            if not (_name(below) == n and _props(below).get("half") == "lower"):
                b[_add(p, "down")] = _with(st, half="lower") if not below else below
                if not below:
                    c.fix("halves", "Added the missing bottom half of doors and tall plants")
                else:
                    del b[p]; c.fix("removed", "Removed a door/plant top half with no bottom half")
        return

    # ---- beds: both halves
    if n and n.endswith("_bed"):
        f, part = pr.get("facing", "north"), pr.get("part")
        other = _add(p, f if part == "foot" else OPP[f])
        if not (_name(b.get(other)) == n and _props(b[other]).get("part") != part):
            if b.get(other) is None:
                b[other] = _with(st, part="head" if part == "foot" else "foot"); c.fix("halves", "Added the missing half of beds")
            else:
                del b[p]; c.fix("removed", "Removed a half-bed that had no second half")
        return

    # ---- plants and crops
    if n and (SOIL_PLANTS.match(n) or n in CROPS or n in ("cactus", "sugar_cane", "nether_wart", "lily_pad", "kelp", "seagrass", "bamboo")):
        bn = _name(below)
        if n in CROPS:
            ok = bn == "farmland"
        elif n == "cactus":
            ok = bn in SAND or bn == "cactus"
        elif n == "sugar_cane":
            ok = bn == "sugar_cane" or (bn in SOIL | SAND and any("water" in (_name(c.get(_add(p, "down"), d)) or "") for d in HORIZ))
        elif n == "nether_wart":
            ok = bn == "soul_sand"
        elif n == "lily_pad":
            ok = bn == "water"
        elif n in ("kelp", "seagrass"):
            ok = bool(bn) and (bn in ("water", "kelp", "kelp_plant") or _solid(below))
        elif n == "bamboo":
            ok = bn in SOIL | SAND | {"bamboo", "gravel"}
        else:
            ok = bn in SOIL
        if not ok:
            _soil_problem(c, p, n, final)
        return

    # ---- gravity blocks hanging in mid-air
    if n and (n in GRAVITY or n.endswith("_concrete_powder")) and not below:
        if final:
            repl = GRAVITY.get(n) or n.replace("_concrete_powder", "_concrete")
            b[p] = f"minecraft:{repl}"
            c.fix("gravity", f"Floating sand/gravel/concrete powder (it would fall) was swapped for a solid block")
        else:
            c.problem("gravity", p, f"{n} has air under it and will fall")
        return

    # ---- things that just need a non-air block below
    if n and (n.endswith("_carpet") or n == "moss_carpet" or n in ("snow", "cake", "flower_pot") or n.startswith("potted_")):
        if not below:
            if final:
                del b[p]; c.fix("removed", "Removed carpets/snow/pots floating over nothing")
            else:
                c.problem("floor", p, f"{n} has nothing under it")
        return
    # ---- candles, pressure plates, standing signs/banners, sea pickles need a sturdy top
    if n and (n.endswith("candle") or n.endswith("_pressure_plate") or (n.endswith(("_sign", "_banner")) and "_wall_" not in n and "hanging" not in n)):
        if not _floor_ok(below):
            if final:
                del b[p]; c.fix("removed", "Removed candles/plates/signs with nothing sturdy under them")
            else:
                c.problem("floor", p, f"{n} needs a solid block under it")
        return
    if n and n.endswith("_hanging_sign") and "_wall_" not in n:
        if not _hang_ok(above):
            if final:
                del b[p]; c.fix("removed", "Removed hanging signs with nothing above them")
            else:
                c.problem("hang", p, f"{n} has nothing to hang from")


def _soil_problem(c, p, n, final, double=False):
    if final:
        del c.b[p]
        if double and _add(p, "up") in c.b:
            del c.b[_add(p, "up")]
        c.fix("removed", "Removed plants and crops that had no soil (they would pop off the moment the world updates)")
    else:
        c.problem("soil", p, f"{n} is not on the soil it needs")


def _check_ids(c, final, version):
    """Block ids that don't exist in this game version or in the player's modpack."""
    names = Counter(s.split("[", 1)[0] for s in c.b.values())
    vanilla = modlib.vanilla_ids(version) if version else None
    pack = c.pack
    pack_blocks = modlib.enabled_blocks(pack) if pack else set()
    bad = {}
    for full in names:
        ns, _, nm = full.partition(":")
        if ns == "minecraft":
            if vanilla is None or nm in vanilla:
                continue
            repl = modlib.RENAMES.get(nm) or modlib.closest(nm, vanilla, 0.86)
            if repl and repl in vanilla:
                bad[full] = ("rename", f"minecraft:{repl}")
            else:
                bad[full] = ("unknown", None)
        else:
            if full in pack_blocks:
                continue
            repl = modlib.closest(full, pack_blocks, 0.9) if pack_blocks else None
            bad[full] = ("rename", repl) if repl else ("mod", None)
    if not bad:
        return
    swaps = {k: v[1] for k, v in bad.items() if v[0] == "rename"}
    if swaps:
        for p, st in list(c.b.items()):
            base = st.split("[", 1)[0]
            if base in swaps:
                c.b[p] = swaps[base] + (st[len(base):])
        c.fix("rename", "Corrected block names that don't exist: " + ", ".join(f"{a.split(':', 1)[1]} → {b.split(':', 1)[1]}" for a, b in list(swaps.items())[:4]))
    left = [k for k, v in bad.items() if v[0] != "rename"]
    unknown_vanilla = [k for k in left if bad[k][0] == "unknown"]
    mod_blocks = [k for k in left if bad[k][0] == "mod"]
    if unknown_vanilla:
        if final:
            for p, st in list(c.b.items()):
                if st.split("[", 1)[0] in unknown_vanilla:
                    del c.b[p]
            c.fix("removed", "Removed blocks that don't exist in Minecraft " + str(version) + ": " + ", ".join(unknown_vanilla[:4]))
        else:
            c.problems.append(f"These blocks don't exist in Minecraft {version}: {', '.join(unknown_vanilla[:6])}. Use real vanilla block ids.")
    if mod_blocks:
        why = "they aren't in your selected modpack" if pack else "no modpack is selected"
        if final:
            for p, st in list(c.b.items()):
                if st.split("[", 1)[0] in mod_blocks:
                    c.b[p] = "minecraft:stone_bricks"
            c.fix("removed", f"Replaced modded blocks with stone bricks because {why}: " + ", ".join(mod_blocks[:4]))
        else:
            c.problems.append(f"These modded blocks can't be used ({why}): {', '.join(mod_blocks[:6])}. Use vanilla blocks or ones from the pack.")


_BOOL = {"waterlogged", "hanging", "powered", "open", "lit", "persistent", "snowy", "locked", "triggered", "inverted", "enabled",
         "extended", "attached", "bottom", "conditional", "disarmed", "drag", "eye", "has_book", "occupied", "in_wall", "unstable",
         "signal_fire", "short", "berries", "cracked", "crafting", "ominous", "tip", "slot_0_occupied"}
_INT = {"age": (0, 25), "level": (0, 15), "rotation": (0, 15), "power": (0, 15), "delay": (1, 4), "bites": (0, 6),
        "layers": (1, 8), "distance": (0, 7), "moisture": (0, 7), "charges": (0, 4), "candles": (1, 4), "eggs": (1, 4),
        "hatch": (0, 2), "pickles": (1, 4), "stage": (0, 1), "honey_level": (0, 5), "note": (0, 24), "flower_amount": (1, 4),
        "segment_amount": (1, 4), "dusted": (0, 3)}
_ENUM = {"facing": {"north", "south", "east", "west", "up", "down"}, "half": {"top", "bottom", "upper", "lower"},
         "axis": {"x", "y", "z"}, "part": {"head", "foot"}, "face": {"floor", "wall", "ceiling"}, "hinge": {"left", "right"},
         "type": {"top", "bottom", "double", "single", "left", "right", "normal", "sticky"},
         "attachment": {"floor", "ceiling", "single_wall", "double_wall"}, "vertical_direction": {"up", "down"}}
_SIDES = {"north", "south", "east", "west"}
_SIDE_VALS = {"true", "false", "none", "low", "tall", "side", "up"}
_HORIZ_ONLY = re.compile(r"(_stairs$|_door$|_trapdoor$|_wall_sign$|_wall_hanging_sign$|_wall_banner$|_wall_torch$|^ladder$|_fence_gate$|"
                         r"_glazed_terracotta$|^(furnace|blast_furnace|smoker|chest|trapped_chest|ender_chest|lectern|loom|stonecutter|"
                         r"carved_pumpkin|jack_o_lantern|repeater|comparator|campfire|soul_campfire|anvil|chipped_anvil|damaged_anvil)$|_bed$)")


def _check_states(c):
    """Block settings that don't exist (facing=left, half=middle, age=99) make the game drop or mangle the block."""
    for p, st in list(c.b.items()):
        if "[" not in st:
            continue
        n = _name(st)
        base = st.split("[", 1)[0]
        pr = _props(st)
        new, changed = {}, False
        for k, v in pr.items():
            keep = v
            if k in _BOOL:
                if v not in ("true", "false"):
                    keep = None
            elif k in _INT:
                lo, hi = _INT[k]
                try:
                    keep = str(min(hi, max(lo, int(v))))
                except ValueError:
                    keep = None
            elif k in _SIDES:
                if v not in _SIDE_VALS:
                    keep = None
            elif k in _ENUM and v not in _ENUM[k]:
                keep = None
                if k == "half" and n:
                    if n.endswith("_door") or n in DOUBLE:
                        keep = "lower"
                    elif n.endswith(("_stairs", "_trapdoor")):
                        keep = "bottom"
            if k == "facing" and keep in ("up", "down") and n and _HORIZ_ONLY.search(n):
                keep = "north"
            if keep != v:
                changed = True
            if keep is not None:
                new[k] = keep
        if changed:
            c.b[p] = base + ("[" + ",".join(f"{k}={v}" for k, v in new.items()) + "]" if new else "")
            c.fix("states", "Fixed block settings that don't exist (a wrong facing, half or other value)")


def process(blocks, final=False, version=None, pack="auto"):
    """Fix and check `blocks` ({(x,y,z): state}) in place. Returns {'fixed': [...], 'problems': [...]}.
    pack: a modpack index, None for vanilla only, or "auto" for the pack selected in Settings."""
    if pack == "auto":
        pack = modlib.active_pack()
    if version is None:
        version = (pack or {}).get("mc") or store.load_settings().get("target_version") or "1.21.1"
    c = Ctx(blocks)
    c.pack = pack
    try:
        _check_ids(c, final, version)
    except Exception:                                      # noqa: BLE001 - never lose a build over the checker
        pass
    try:
        _check_states(c)
    except Exception:                                      # noqa: BLE001
        pass
    for p in sorted(blocks, key=lambda q: (q[1], q[0], q[2])):          # bottom-up so supports are settled first
        st = blocks.get(p)
        if st is None:
            continue
        try:
            _check_block(c, p, st, final)
        except Exception:                                  # noqa: BLE001
            continue
    if c.fixes:
        rs._fix_connections(blocks)                        # new fences/etc. need their connections worked out
        rs._fix_dust(blocks)
    fixed = [f"{t} (×{n})" if n > 1 else t for t, n in c.fixes.items()]
    return {"fixed": fixed, "problems": c.problems}
