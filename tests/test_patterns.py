import unittest

from tests import _env  # noqa: F401
from blockforge import checks, patterns, sandbox

KINDS = ("buried_path", "jump_step", "door_blocked", "floating", "headroom", "wrong_facing", "corner_turn")

CASES = {
    "stair_run_east": lambda: patterns.straight_stair_run(2, 1, 2, "east", 6, 3),
    "stair_run_north": lambda: patterns.straight_stair_run(10, 3, 10, "north", 5, 2, "spruce"),
    "stair_run_west": lambda: patterns.straight_stair_run(10, 3, 4, "west", 4, 1, landing=0),
    "switchback": lambda: patterns.switchback_landing(2, 1, 2, "south", 4, 2),
    "switchback_east": lambda: patterns.switchback_landing(2, 1, 2, "east", 5, 3),
    "lantern_japanese": lambda: patterns.lantern_post(3, 1, 3, "japanese"),
    "lantern_medieval": lambda: patterns.lantern_post(3, 1, 3, "medieval"),
    "lantern_modern": lambda: patterns.lantern_post(3, 1, 3, "modern"),
    "lantern_nordic": lambda: patterns.lantern_post(3, 1, 3, "nordic"),
    "door_north": lambda: patterns.doorway(5, 1, 5, "north", "dark_oak"),
    "door_east": lambda: patterns.doorway(5, 1, 5, "east", "spruce"),
    "window_south": lambda: patterns.window(5, 2, 5, "south"),
    "window_west": lambda: patterns.window(5, 2, 5, "west", "glass_pane"),
    "house_x": lambda: patterns.gable_roof_house_shell(0, 0, 8, 6, 1, 5, "white_terracotta", "spruce_stairs", "spruce"),
    "house_z": lambda: patterns.gable_roof_house_shell(0, 0, 6, 9, 1, 4, "spruce_planks", "oak_stairs", "oak", "east"),
    "bridge": lambda: patterns.stone_arch_bridge(2, 6, 2, 11, 3),
    "bridge_wide": lambda: patterns.stone_arch_bridge(2, 5, 2, 8, 5),
    "tree_oak": lambda: patterns.tree("oak", 4, 1, 4, 6),
    "tree_birch": lambda: patterns.tree("birch", 4, 1, 4, 6),
    "tree_spruce": lambda: patterns.tree("spruce", 4, 1, 4, 9),
    "tree_dark_oak": lambda: patterns.tree("dark_oak", 4, 1, 4, 6),
    "tree_maple": lambda: patterns.tree("maple", 4, 1, 4, 6),
}


class Patterns(unittest.TestCase):
    def test_every_pattern_is_clean(self):
        for name, make in CASES.items():
            with self.subTest(name):
                blocks, meta = sandbox.run_safe(make())
                self.assertTrue(blocks)
                found = [f for f in checks.run(blocks) if f["check"] in KINDS]
                self.assertEqual(found, [], [f["text"] for f in found])
                self.assertEqual(meta.get("warnings"), [])
                self.assertEqual(meta.get("fixes"), [])

    def test_stairs_face_uphill(self):
        blocks, _ = sandbox.run_safe(patterns.straight_stair_run(0, 1, 0, "east", 4, 1))
        for i in range(4):
            self.assertIn("facing=east", blocks[(i, 1 + i, 0)])
            self.assertIn("half=bottom", blocks[(i, 1 + i, 0)])

    def test_switchback_climbs_twice(self):
        blocks, _ = sandbox.run_safe(patterns.switchback_landing(0, 1, 0, "south", 4, 2))
        self.assertEqual(max(p[1] for p in blocks), 1 + 2 * 4 - 1)

    def test_house_has_door_and_roof(self):
        blocks, _ = sandbox.run_safe(patterns.gable_roof_house_shell(0, 0, 8, 6, 1, 5))
        self.assertTrue(any("_door" in s for s in blocks.values()))
        self.assertTrue(any("stairs" in s for s in blocks.values()))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            patterns.straight_stair_run(0, 0, 0, "up", 3)
        with self.assertRaises(ValueError):
            patterns.tree("palm", 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
