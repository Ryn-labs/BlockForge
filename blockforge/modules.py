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
    _ctx["modules"].append({"name": "item sorter", "cells": dict(cells), "clear": clear})
    return {"input": F.pos(0, 4, 4) if input_chest else F.pos(0, 3, 4), "overflow": F.pos(n, 3, 4) if overflow_chest else None,
            "chests": [F.pos(i, 1, 5) for i in range(n)], "size": (n + (1 if overflow_chest else 0), 5 if input_chest else 4, 6)}


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


EXPORTS = ["item_sorter"]
