"""The house check can never break the other checks: an error inside it is caught and noted, giant builds are skipped
with a note, slow runs stop at the time budget with a note, and odd block dicts don't raise."""
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from blockforge import checks, house


def box(n=6):
    C = {}
    for x in range(n):
        for z in range(n):
            C[(x, 0, z)] = "minecraft:stone_bricks"
    for y in (1, 2, 3):
        for x in range(n):
            for z in (0, n - 1):
                C[(x, y, z)] = "minecraft:oak_planks"
                C[(z, y, x)] = "minecraft:oak_planks"
    for x in range(n):
        for z in range(n):
            C[(x, 4, z)] = "minecraft:spruce_planks"
    return C


class HouseGuard(unittest.TestCase):
    def test_internal_error_is_caught_and_noted(self):
        with mock.patch.object(house, "findings", side_effect=RuntimeError("boom")):
            found = checks.run(box())
        self.assertIsInstance(found, list)
        self.assertTrue(any("internal error" in n for n in house.NOTES))
        self.assertIn("house check skipped", checks.summary(found))

    def test_giant_build_is_skipped_with_a_note(self):
        with mock.patch.object(house, "MAX_BLOCKS", 50):
            found = checks.run(box())
        self.assertFalse([f for f in found if f["check"] in ("door_unreachable", "dark_spawn_spot", "roof_hole")])
        self.assertTrue(any("over the 50 limit" in n for n in house.NOTES))

    def test_time_budget_stops_early_with_a_note(self):
        out = house.findings(box(), budget=-1)
        self.assertEqual(out, [])
        self.assertTrue(any("stopped after" in n for n in house.NOTES))

    def test_notes_reset_on_a_normal_run(self):
        house.NOTES[:] = ["old note"]
        checks.run(box())
        self.assertNotIn("old note", house.NOTES)

    def test_malformed_block_dicts_do_not_raise(self):
        odd = [
            {},
            {(0, 0, 0): "minecraft:air"},
            {(0, 0, 0): "stone", (1, 0, 0): "minecraft:oak_stairs[facing=sideways,half=middle]"},
            {(0, 0, 0): "minecraft:", (0, 1, 0): "[]", (0, 2, 0): "minecraft:oak_door[half=upper]"},
            {(-10**6, 5, 10**6): "minecraft:stone", (10**6, -64, -10**6): "minecraft:lantern[hanging=true]"},
            {(x, y, 0): "minecraft:glass" for x in range(40) for y in range(40)},
        ]
        for C in odd:
            with self.subTest(n=len(C)):
                found = checks.run(C)
                self.assertIsInstance(found, list)
                checks.summary(found)


if __name__ == "__main__":
    unittest.main()
