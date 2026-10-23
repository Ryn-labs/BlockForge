"""Mobs and in-game tests for build scripts.

entity() puts a mob into the build (it is saved in every export). The test_* functions describe how to PROVE a
redstone build or farm works. BlockForge's test lab places the build in a hidden Minecraft server, runs these steps
at high speed and checks the results before the build is shown to the player."""
import re

_ctx = {}


def bind(entities, tests, error):
    _ctx.update(entities=entities, tests=tests, error=error)


def _id(s):
    s = str(s).strip().lower().replace(" ", "_").split("[", 1)[0]
    return s if ":" in s else "minecraft:" + s


_PROFESSIONS = {"none", "armorer", "butcher", "cartographer", "cleric", "farmer", "fisherman", "fletcher", "leatherworker",
                "librarian", "mason", "nitwit", "shepherd", "toolsmith", "weaponsmith"}


def entity(x, y, z, kind, name=None, profession=None, baby=False, no_ai=False, silent=False):
    """Put a mob in the build at block (x, y, z) (it stands on the block below). It never despawns.
    kind: 'villager', 'zombie', 'iron_golem', 'cow', 'sheep', 'chicken'...  name: a name tag.
    profession (villagers): 'none', 'farmer', 'nitwit'..."""
    kid = _id(kind)
    data = {"id": kid, "PersistenceRequired": True}
    if name:
        data["CustomName"] = str(name)[:40]
    if kid == "minecraft:villager":
        prof = str(profession or "none").lower()
        if prof not in _PROFESSIONS:
            raise ValueError(f"unknown villager profession '{prof}'")
        data["VillagerData"] = {"profession": "minecraft:" + prof, "level": 1, "type": "minecraft:plains"}
    if baby:
        data["Age"] = -24000
    if no_ai:
        data["NoAI"] = True
    if silent:
        data["Silent"] = True
    _ctx["entities"].append([float(x) + 0.5, float(y), float(z) + 0.5, data])


# ---------------------------------------------------------------- test steps (coordinates are the build's own)
def _p(x, y, z):
    return [int(round(x)), int(round(y)), int(round(z))]


def test_put(x, y, z, item, count=64):
    """Put items into the container (chest, hopper, barrel, dispenser...) at (x, y, z)."""
    _ctx["tests"].append({"do": "put", "pos": _p(x, y, z), "item": _id(item), "count": max(1, int(count))})


def test_press(x, y, z, ticks=20):
    """Press the button / flip the lever at (x, y, z) (a lever stays on, a button lets go after `ticks`)."""
    _ctx["tests"].append({"do": "press", "pos": _p(x, y, z), "ticks": max(1, int(ticks))})


def test_power(x, y, z, on=True):
    """Put (or remove) a redstone block at (x, y, z) to power the circuit from there (it must be an empty spot)."""
    _ctx["tests"].append({"do": "power", "pos": _p(x, y, z), "on": bool(on)})


def test_wait(seconds=None, ticks=None):
    """Let the game run (fast) for a while. 20 ticks = 1 second; a Minecraft day is 24000 ticks (20 minutes)."""
    t = int(ticks) if ticks is not None else int(float(seconds or 10) * 20)
    _ctx["tests"].append({"do": "wait", "ticks": max(1, min(t, 240000))})


def test_expect_items(x, y, z, item, at_least=1, at_most=None):
    """Check the container at (x, y, z) holds at least / at most this many of `item`."""
    _ctx["tests"].append({"do": "expect_items", "pos": _p(x, y, z), "item": _id(item), "at_least": int(at_least),
                          "at_most": None if at_most is None else int(at_most)})


def test_expect_block(x, y, z, block):
    """Check the block at (x, y, z) is `block` (e.g. 'air' after a door opened, 'redstone_lamp[lit=true]')."""
    _ctx["tests"].append({"do": "expect_block", "pos": _p(x, y, z), "block": str(block).strip().lower()})


def test_expect_mob(kind, x1, y1, z1, x2, y2, z2, at_least=1, at_most=None):
    """Check how many of a mob are inside a box (e.g. villagers still in their cells, a golem got killed)."""
    _ctx["tests"].append({"do": "expect_mob", "kind": _id(kind), "box": _p(x1, y1, z1) + _p(x2, y2, z2),
                          "at_least": int(at_least), "at_most": None if at_most is None else int(at_most)})


def test_note(text):
    """A line explaining what the test proves (shown to the player)."""
    _ctx["tests"].append({"do": "note", "text": str(text)[:200]})


EXPORTS = ["entity", "test_put", "test_press", "test_power", "test_wait", "test_expect_items", "test_expect_block",
           "test_expect_mob", "test_note"]
_NAME_OK = re.compile(r"^[a-z0-9_:.\[\]=,-]+$")
