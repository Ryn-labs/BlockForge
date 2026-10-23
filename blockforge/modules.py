"""Proven redstone machines, placed block-for-block so they work in game.

The AI must never wire these by hand: it calls the function and decorates around the result. Every block a module
places is locked (the runner rejects a script that overwrites one), and the cells a module needs kept clear are
checked too.

Item sorter (one "slice" per sorted item, slices side by side along the hopper line):

    side view of one slice (back on the left, chest on the right; v = 0..5, y = 0..3)

        y3                          [chain hopper ->next slice]
        y2        dust  dust  [comparator] [filter hopper]  (air above the chest)
        y1  dust  block block [block]      [lock hopper]  -> [chest]
        y0  block [repeater] block [torch on block]

    - The filter hopper holds 41 of its item (10 for items that stack to 16) plus one named junk stick in each other
      slot. Its comparator reads 2. One extra item makes it read 3.
    - 3 dust (C, B, A) means only a 3 reaches the end. A powers the block under it, the repeater carries that into
      the torch's block, the torch turns off and the lock hopper pulls one item down into the chest.
    - Neighbouring slices' dust touches, but a 3 has faded to 0 by the time it would reach the next slice's end.
    - With junk in the other 4 slots the filter can never read more than 3, so a full chest can't break anything.
"""
import re

from . import redstone as rs

_ctx = {}


def bind(blocks, tiles, modules, place, error):
    _ctx.update(blocks=blocks, tiles=tiles, modules=modules, place=place, error=error)


_CW = {"east": "south", "south": "west", "west": "north", "north": "east"}
_CCW = {v: k for k, v in _CW.items()}

STACK16 = re.compile(r"^(ender_pearl|egg|blue_egg|brown_egg|snowball|bucket|honey_bottle|armor_stand|.*_sign|.*_hanging_sign|"
                     r".*_banner|written_book)$")
UNSTACKABLE = re.compile(r"(_sword|_pickaxe|_axe|_shovel|_hoe|_helmet|_chestplate|_leggings|_boots|_horse_armor|_boat|"
                         r"_chest_boat|minecart|^bow$|^crossbow$|^trident$|^shield$|^elytra$|^totem_of_undying$|potion$|"
                         r"^saddle$|^mace$|_bucket$|^cake$|_bed$|shulker_box$|^music_disc|^enchanted_book$|^writable_book$|"
                         r"^fishing_rod$|^flint_and_steel$|^shears$|^brush$|^spyglass$|^carrot_on_a_stick$|_on_a_stick$|"
                         r"^goat_horn$|^bundle$|_bundle$|^suspicious_stew$|_stew$|^rabbit_stew$|^beetroot_soup$|^wolf_armor$)")
JUNK = {"id": "minecraft:stick", "name": "Sorter filter (don't remove)"}


def _item_id(item):
    s = str(item).strip().lower().replace(" ", "_")
    s = s.split("[", 1)[0]
    return s if ":" in s else "minecraft:" + s


def filter_count(item):
    """How many of `item` the filter hopper holds (comparator reads 2; one more makes 3)."""
    n = _item_id(item).split(":", 1)[1]
    if UNSTACKABLE.search(n) and not n == "bucket":
        raise ValueError(f"{n} doesn't stack, so a hopper sorter can't sort it")
    return 10 if STACK16.match(n) else 41


class _Frame:
    """Local coords (u along the hopper line, y, v from back to front) -> world coords and directions."""

    def __init__(self, x, y, z, facing):
        f = rs._dir(facing)
        self.o = (int(x), int(y), int(z))
        self.d = {"front": f, "back": rs.OPP[f], "along": _CCW[f], "against": rs.OPP[_CCW[f]]}

    def pos(self, u, y, v):
        a, fr = rs.DIRS[self.d["along"]], rs.DIRS[self.d["front"]]
        return (self.o[0] + u * a[0] + v * fr[0], self.o[1] + y, self.o[2] + u * a[2] + v * fr[2])


def item_sorter(x, y, z, items, facing="south", block="stone_bricks", input_chest=True, overflow_chest=True):
    """A tileable, overflow-safe hopper ITEM SORTER that works in survival.

    items: one item id per slice, e.g. ["cobblestone", "iron_ingot", "oak_log"]. Every slice gets its own chest.
    facing: the side the chests face (the front of the machine).
    (x, y, z) is the back-bottom corner of the first slice. The machine is len(items) wide (+1 for the overflow chest)
    along the hopper line, 6 deep and 5 tall (the input chest sits on top of the first slice).
    Items go into the input chest (or any hopper on the line). Unsorted items end up in the overflow chest.
    Returns {'input': pos, 'overflow': pos, 'chests': [pos...], 'size': (along, height, depth)}.
    Do NOT place, replace or wire anything inside it. Build walls, floors and decoration around it instead.
    """
    items = [_item_id(i) for i in (items or [])]
    if not items:
        raise ValueError("item_sorter needs at least one item")
    if len(items) > 120:
        raise ValueError("item_sorter: at most 120 items")
    counts = [filter_count(i) for i in items]
    F = _Frame(x, y, z, facing)
    d = F.d
    base = "minecraft:" + str(block).replace("minecraft:", "")
    cells, clear = {}, []

    def put(u, yy, v, st, tile=None):
        p = F.pos(u, yy, v)
        cells[p] = st
        if tile:
            _ctx["tiles"][p] = tile

    st = rs._st
    n = len(items)
    for i, (item, cnt) in enumerate(zip(items, counts)):
        put(i, 0, 0, base)
        put(i, 1, 0, st("redstone_wire", east="none", north="none", south="none", west="none", power=0))       # dust A
        put(i, 0, 1, st("repeater", facing=d["back"], delay=1, locked="false", powered="false"))
        put(i, 1, 1, base)
        put(i, 2, 1, st("redstone_wire", east="none", north="none", south="none", west="none", power=0))       # dust B
        put(i, 0, 2, base)                                                                                     # torch block
        put(i, 1, 2, base)
        put(i, 2, 2, st("redstone_wire", east="none", north="none", south="none", west="none", power=0))       # dust C
        put(i, 0, 3, st("redstone_wall_torch", facing=d["front"], lit="true"))
        put(i, 1, 3, base)
        put(i, 2, 3, st("comparator", facing=d["front"], mode="compare", powered="false"))
        put(i, 0, 4, base)
        put(i, 1, 4, st("hopper", facing=d["front"], enabled="false"))                                         # lock hopper
        put(i, 2, 4, st("hopper", facing=d["back"], enabled="true"),                                           # filter
            tile={"id": "minecraft:hopper", "items": [{"slot": 0, "id": item, "count": cnt}] +
                  [{"slot": s, "id": JUNK["id"], "count": 1, "name": JUNK["name"]} for s in range(1, 5)]})
        put(i, 3, 4, st("hopper", facing=d["along"], enabled="true"))                                          # item line
        put(i, 0, 5, base)
        put(i, 1, 5, st("chest", facing=d["front"], type="single", waterlogged="false"),
            tile={"id": "minecraft:chest", "items": [], "name": item.split(":", 1)[1].replace("_", " ").title()})
        clear += [F.pos(i, 2, 0), F.pos(i, 2, 5)]            # dust A must see up to B; the chest needs room to open
    if input_chest:
        put(0, 4, 4, st("chest", facing=d["front"], type="single", waterlogged="false"),
            tile={"id": "minecraft:chest", "items": [], "name": "Sorter input"})
    if overflow_chest:
        put(n, 3, 4, st("chest", facing=d["front"], type="single", waterlogged="false"),
            tile={"id": "minecraft:chest", "items": [], "name": "Overflow"})
        clear.append(F.pos(n, 4, 4))
    for p, s in cells.items():
        _ctx["place"](*p, s)
    tests = []
    if input_chest and overflow_chest:                    # self-test for the test lab: a stack of each + some junk
        junk = next(j for j in ("minecraft:dirt", "minecraft:gravel", "minecraft:andesite", "minecraft:clay_ball")
                    if j not in items)
        sample = list(zip(items, counts))[:20]
        tests.append({"do": "note", "text": f"Item sorter: one stack of each of {len(sample)} items plus 64 unsorted "
                                            f"{junk.split(':')[1]} go in the input chest"})
        inp = list(F.pos(0, 4, 4))
        for item, cnt in sample:
            tests.append({"do": "put", "pos": inp, "item": item, "count": 16 if cnt == 10 else 64})
        tests.append({"do": "put", "pos": inp, "item": junk, "count": 64})
        tests.append({"do": "wait", "ticks": (len(sample) + 1) * 64 * 8 + 40 * n + 600})
        for i, (item, cnt) in enumerate(sample):
            tests.append({"do": "expect_items", "pos": list(F.pos(i, 1, 5)), "item": item,
                          "at_least": 15 if cnt == 10 else 63, "at_most": None})
        tests.append({"do": "expect_items", "pos": list(F.pos(n, 3, 4)), "item": junk, "at_least": 64, "at_most": None})
    _ctx["modules"].append({"name": "item sorter", "cells": dict(cells), "clear": clear, "tests": tests})
    return {"input": F.pos(0, 4, 4) if input_chest else F.pos(0, 3, 4), "overflow": F.pos(n, 3, 4) if overflow_chest else None,
            "chests": [F.pos(i, 1, 5) for i in range(n)], "size": (n + (1 if overflow_chest else 0), 5 if input_chest else 4, 6)}


def iron_farm(x, y, z, facing="south", block="stone_bricks", lift=8, _sight="fence"):
    """A villager-panic IRON FARM, proven in the game: about 80-150 iron per hour while its chunks are loaded.

    3 villagers with beds see a name-tagged zombie over a fence and summon iron golems onto the spawn floor below;
    golems walk/are pushed under a lava blade and the iron drops into hoppers that fill the collection chest. A
    daylight-sensor shutter hides the zombie at night so the villagers can sleep (only rested villagers summon).
    facing = the side the collection chest is on (the front).
    (x, y, z) is the back-left corner at ground level. The farm floor is `lift` blocks up (golems must not be able to
    spawn on the ground near it), so it is 12 wide, 10 deep and lift+9 tall. Returns {'chest', 'size'}.
    Do NOT build inside it, cover its spawn floor, or put blocks within 8 blocks of the villagers that golems
    could spawn on (keep the surroundings glass, leaves, slabs or open air).
    """
    F = _Frame(x, y, z, facing)
    d = F.d
    base = "minecraft:" + str(block).replace("minecraft:", "")
    L = int(lift)
    st = rs._st
    cells, clear, ents = {}, [], []

    def put(u, yy, v, s):
        cells[F.pos(u, yy, v)] = s

    glass = "minecraft:glass"
    leaves = st("oak_leaves", persistent="true", distance=1, waterlogged="false")
    for u, v in ((-1, -1), (9, -1), (-1, 9), (9, 9), (4, -1), (4, 9)):              # stilts
        for yy in range(0, L):
            put(u, yy, v, base)
    for u in range(0, 9):
        for v in range(0, 8):
            # spawn floor. Next to the walls it's glass: a golem (1.4 wide) appearing there would be stuck in the wall,
            # alive, and villagers stop summoning while they can see a living golem
            put(u, L, v, glass if (u in (0, 8) or v == 0) else base)
        put(u, L, 8, st("hopper", facing=d["along"], enabled="true"))             # kill row collects the iron
        put(u, L + 1, 0, "minecraft:water")                                      # stream pushes golems to the front
        put(u, L + 2, 8, st("crimson_wall_sign", facing=d["back"], waterlogged="false"))
        put(u, L + 3, 8, "minecraft:lava")                                       # lava blade at golem head height
        put(u, L + 3, 7, st("crimson_hanging_sign", rotation=0, attached="false", waterlogged="false"))
        put(u, L + 4, 7, glass)
        put(u, L + 4, 8, glass)
    put(9, L, 8, st("hopper", facing=d["along"], enabled="true"))
    put(10, L, 8, st("chest", facing=d["front"], type="single", waterlogged="false"))
    put(10, L + 1, 8, leaves)                                                    # no golem can spawn on the chest
    for v in range(-1, 10):                                                      # glass walls round the spawn floor
        for yy in range(L, L + 4):
            put(-1, yy, v, glass)
            if not (v == 8 and yy == L):
                put(9, yy, v, glass)
    for u in range(-1, 10):
        for yy in range(L, L + 4):
            put(u, yy, -1, glass)
            put(u, yy, 9, glass)
    if _sight == "fence":
        # villager pod right above the lava blade (golems like to stay near villagers, so they walk the same way the
        # water pushes them). Villagers must SEE the zombie, and glass blocks a mob's view, so the two are kept apart
        # by fences: 1.5 high, so nothing can jump them, while both mobs' eyes (1.62 / 1.74 up) look over the top.
        fence = st("crimson_fence", east="false", north="false", south="false", west="false", waterlogged="false")
        for u in range(1, 8):
            for v in range(6, 11):
                put(u, L + 4, v, glass)
                put(u, L + 8, v, glass)
                for yy in range(L + 5, L + 8):
                    if v == 6:
                        if yy == L + 5:
                            put(u, yy, v, fence)                  # villagers' front: a fence, open above it
                        else:
                            clear.append(F.pos(u, yy, v))
                    elif u in (1, 3, 5, 7) or v == 10:
                        put(u, yy, v, glass)
        for u in (2, 4, 6):
            put(u, L + 5, 8, st("red_bed", facing=d["front"], part="foot", occupied="false"))
            put(u, L + 5, 9, st("red_bed", facing=d["front"], part="head", occupied="false"))
            for yy in (L + 5, L + 6, L + 7):
                clear.append(F.pos(u, yy, 7))
            ents.append((u, L + 5, 7, "villager", None))         # stands on the floor in front of its bed
        for u in range(3, 6):
            for v in range(3, 6):
                put(u, L + 4, v, glass)
                if (u, v) == (4, 4):
                    put(u, L + 7, v, leaves)                       # shade: the sun can't burn the zombie
                elif v == 5:
                    put(u, L + 5, v, fence)                        # zombie's front: a fence, open above it
                    clear += [F.pos(u, L + 6, v)]
                    put(u, L + 7, v, glass)
                else:
                    for yy in (L + 5, L + 6, L + 7):
                        put(u, yy, v, glass)
        clear += [F.pos(4, L + 5, 4), F.pos(4, L + 6, 4)]
        ents.append((4, L + 5, 4, "zombie", "Iron farm zombie"))
        # Night shutter: villagers that can see the zombie panic all night and never sleep, and only villagers that
        # slept summon golems. So after dark a sticky piston (powered by an inverted daylight sensor) slides a block in
        # front of the zombie's face; at dawn it pulls it back and the rested villagers panic and summon all day.
        put(4, L + 7, 5, base)                                                    # the shutter block (pushable)
        put(4, L + 8, 5, st("sticky_piston", facing="down", extended="false"))
        put(4, L + 9, 5, st("daylight_detector", inverted="true", power=0))
        put(4, L + 10, 5, glass)                                                  # sky light gets through; golems can't spawn on it
        vil_box, zom_box = (F.pos(1, L + 5, 6), F.pos(7, L + 7, 10)), (F.pos(3, L + 5, 3), F.pos(5, L + 6, 5))
    else:
        # villager pod right above the lava blade: golems like to stay near villagers, so they walk the same way the
        # water pushes them, into the lava (with the villagers over the middle, a golem would stand still under them)
        for u in range(1, 8):
            for v in range(6, 10):
                put(u, L + 4, v, glass)
                put(u, L + 8, v, glass)
                for yy in range(L + 5, L + 8):
                    wall = u in (1, 3, 5, 7) or v in (6, 9)
                    gap = yy == L + 7 and _sight != "glass" and (v == 6 or (_sight == "gaps" and u in (3, 5) and v in (7, 8)))
                    if wall and not gap:                       # eye-level gaps (1 high: nothing fits) so every villager sees the zombie
                        put(u, yy, v, glass)
        for u in (2, 4, 6):
            put(u, L + 5, 7, st("red_bed", facing=d["front"], part="foot", occupied="false"))
            put(u, L + 5, 8, st("red_bed", facing=d["front"], part="head", occupied="false"))
            for yy in (L + 6, L + 7):
                clear += [F.pos(u, yy, 7), F.pos(u, yy, 8)]
            ents.append((u, L + 5, 7, "villager", None))
        # the zombie that scares them: villagers must SEE it (glass blocks a mob's line of sight), so it looks at them
        # through a 1-high gap at eye level that neither it nor the villagers can fit through
        for u in range(3, 6):
            for v in range(3, 6):
                put(u, L + 4, v, glass)
                put(u, L + 5, v, glass)                                # zombie stands one block higher: eyes level with the villagers'
                put(u, L + 8, v, leaves if (u, v) == (4, 4) else glass)
                if (u, v) != (4, 4):
                    put(u, L + 6, v, glass)
                    if v != 5 or _sight == "glass":
                        put(u, L + 7, v, glass)
        if _sight != "glass":
            clear += [F.pos(u, L + 7, 6) for u in range(1, 8)] + [F.pos(u, L + 7, 5) for u in range(3, 6)]
        clear += [F.pos(4, L + 6, 4), F.pos(4, L + 7, 4)]
        ents.append((4, L + 6, 4, "zombie", "Iron farm zombie"))
        vil_box, zom_box = (F.pos(1, L + 5, 6), F.pos(7, L + 7, 9)), (F.pos(3, L + 6, 3), F.pos(5, L + 7, 5))
    for p_, s_ in cells.items():
        _ctx["place"](*p_, s_)
    from . import testkit
    for u, yy, v, kind, nm in ents:
        q = F.pos(u, yy, v)
        testkit.entity(q[0], q[1], q[2], kind, name=nm)
    chest = F.pos(10, L, 8)
    lo, hi = vil_box
    tests = [{"do": "note", "text": "Iron farm: 2 in-game days, then the chest must have iron and every mob must still be in place"},
             {"do": "wait", "ticks": 48000},
             {"do": "expect_items", "pos": list(chest), "item": "minecraft:iron_ingot", "at_least": 25, "at_most": None},
             {"do": "expect_mob", "kind": "minecraft:villager", "box": list(lo) + list(hi), "at_least": 3, "at_most": None}]
    zl, zh = zom_box
    tests.append({"do": "expect_mob", "kind": "minecraft:zombie", "box": list(zl) + list(zh), "at_least": 1, "at_most": None})
    _ctx["modules"].append({"name": "iron farm", "cells": dict(cells), "clear": clear, "tests": tests})
    return {"chest": chest, "size": (12, L + 9, 11)}


def check_intact(blocks):
    """Problems where a script built over a module, or blocked a cell it needs clear."""
    problems = []
    for m in _ctx.get("modules", []):
        bad = [(p, s, blocks.get(p)) for p, s in m["cells"].items() if blocks.get(p) != s]
        blocked = [p for p in m["clear"] if rs._solid(blocks.get(p))]
        for p, want, got in bad[:3]:
            problems.append(f"the {m['name']} was changed at {p}: it needs {want.replace('minecraft:', '')}, "
                            f"found {(got or 'air').replace('minecraft:', '')}")
        for p in blocked[:2]:
            problems.append(f"the {m['name']} needs {p} kept clear (no solid block), found {blocks[p].replace('minecraft:', '')}")
    return problems


def restore(blocks, modules):
    """Put module blocks back exactly (after auto-fixers ran); dust keeps the connections finalize worked out."""
    for m in modules:
        for p, s in m["cells"].items():
            cur = blocks.get(p)
            if s.startswith("minecraft:redstone_wire") and cur and cur.startswith("minecraft:redstone_wire"):
                continue
            blocks[p] = s


EXPORTS = ["item_sorter", "iron_farm"]
