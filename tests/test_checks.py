import unittest

from tests import _env  # noqa: F401
from blockforge import checks, prompts

M = "minecraft:"


def floor(n=6):
    return {(x, 0, z): M + "stone" for x in range(n) for z in range(n)}


def stair(facing, half="bottom"):
    return f"{M}oak_stairs[facing={facing},half={half},shape=straight]"


def slab(kind="bottom"):
    return f"{M}oak_slab[type={kind}]"


def door(facing, half="lower"):
    return f"{M}oak_door[facing={facing},half={half}]"


def of(blocks, check):
    return [f for f in checks.run(blocks) if f["check"] == check]


class Floating(unittest.TestCase):
    def test_positive(self):
        b = floor()
        b[(5, 6, 5)] = M + "stone"
        b[(5, 7, 5)] = M + "stone"
        f = of(b, "floating")
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["at"], [5, 6, 5])
        self.assertIn("2 blocks", f[0]["text"])

    def test_negative(self):
        b = floor()
        b[(2, 1, 2)] = M + "stone"
        b[(2, 2, 2)] = M + "stone"
        self.assertEqual(of(b, "floating"), [])


class BuriedPath(unittest.TestCase):
    def test_positive(self):
        b = floor()
        b[(1, 1, 1)] = stair("east")
        b[(1, 3, 1)] = M + "stone"
        f = of(b, "buried_path")
        self.assertEqual([x["at"] for x in f], [[1, 1, 1]])
        self.assertIn("(1, 1, 1)", f[0]["text"])
        self.assertIn("2 above", f[0]["text"])

    def test_negative(self):
        b = floor()
        b[(1, 1, 1)] = stair("east")
        b[(1, 4, 1)] = M + "stone"
        self.assertEqual(of(b, "buried_path"), [])


class JumpStep(unittest.TestCase):
    def test_positive(self):
        b = floor()
        b[(1, 1, 1)] = slab()
        b[(2, 2, 1)] = slab()                        # 1 block higher than the slab next to it
        self.assertEqual(len(of(b, "jump_step")), 1)

    def test_negative(self):
        b = floor()
        b[(1, 1, 1)] = slab()
        b[(2, 1, 1)] = stair("east")                 # low side meets the slab, climbs half a block
        b[(3, 2, 1)] = stair("east")
        self.assertEqual(of(b, "jump_step"), [])


class CornerTurn(unittest.TestCase):
    def test_positive(self):
        b = floor()
        b[(1, 1, 1)] = stair("east")
        b[(1, 1, 2)] = stair("south")
        f = of(b, "corner_turn")
        self.assertEqual(len(f), 1)
        self.assertIn("(1, 1, 1)", f[0]["text"])

    def test_negative(self):
        b = floor()
        b[(1, 1, 1)] = stair("east")
        b[(1, 1, 2)] = stair("east")                 # side by side, same direction: a wide stair
        self.assertEqual(of(b, "corner_turn"), [])


class WrongFacing(unittest.TestCase):
    def test_positive(self):
        b = floor()
        b[(2, 1, 1)] = stair("east")                 # high side east
        b[(1, 2, 1)] = stair("west")                 # but the path climbs west
        self.assertEqual(len(of(b, "wrong_facing")), 1)

    def test_negative(self):
        b = floor()
        b[(1, 1, 1)] = stair("east")
        b[(2, 2, 1)] = stair("east")
        self.assertEqual(of(b, "wrong_facing"), [])


class DoorBlocked(unittest.TestCase):
    def test_positive(self):
        b = floor()
        b[(3, 1, 3)] = door("north")
        b[(3, 2, 3)] = door("north", "upper")
        b[(3, 1, 2)] = M + "stone_bricks"
        f = of(b, "door_blocked")
        self.assertEqual(len(f), 1)
        self.assertIn("(3, 1, 3)", f[0]["text"])

    def test_negative(self):
        b = floor()
        b[(3, 1, 3)] = door("north")
        b[(3, 2, 3)] = door("north", "upper")
        b[(2, 1, 3)] = M + "stone_bricks"            # beside the door is fine
        self.assertEqual(of(b, "door_blocked"), [])


class Headroom(unittest.TestCase):
    def test_positive(self):
        b = floor()
        b[(1, 1, 1)] = slab()
        b[(1, 3, 1)] = slab("top")                   # not solid, but only 1 free block above the path
        f = of(b, "headroom")
        self.assertEqual(len(f), 1)
        self.assertIn("(1, 1, 1)", f[0]["text"])

    def test_negative(self):
        b = floor()
        b[(1, 1, 1)] = slab()
        b[(1, 4, 1)] = slab("top")
        self.assertEqual(of(b, "headroom"), [])


class Helpers(unittest.TestCase):
    def test_solid_table(self):
        self.assertTrue(checks.is_solid(M + "oak_planks"))
        self.assertTrue(checks.is_solid(M + "stone_bricks"))
        self.assertFalse(checks.is_solid(M + "oak_stairs[facing=east]"))
        self.assertFalse(checks.is_solid(M + "stone_brick_wall"))
        self.assertFalse(checks.is_solid(M + "some_mod:weird_thing"))        # unknown: not solid

    def test_cap_and_count(self):
        b = floor(40)
        for i in range(30):
            b[(i, 5 + i % 2, 39)] = M + "stone"      # 30 separate floating blocks
            b[(i, 20, 38)] = M + "stone"
        f = of(b, "floating")
        self.assertLessEqual(len(f), checks.CAP)
        self.assertGreater(checks.counts(f)["floating"], checks.CAP)


class FixMessage(unittest.TestCase):
    def test_lists_coordinates_and_groups(self):
        b = floor()
        b[(1, 1, 1)] = stair("east")
        b[(1, 3, 1)] = M + "stone"
        b[(5, 6, 5)] = M + "stone"
        found = checks.run(b)
        msg = prompts.checks_fix_message(found)
        self.assertIn("(1, 1, 1)", msg)
        self.assertIn("(5, 6, 5)", msg)
        self.assertIn("Buried path (1):", msg)
        self.assertIn("Floating parts (2):", msg)
        self.assertIn("```python", msg)


if __name__ == "__main__":
    unittest.main()
