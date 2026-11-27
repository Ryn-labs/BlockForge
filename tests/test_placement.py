import unittest

from tests import _env  # noqa: F401
from blockforge import placement


class FinalRemovalReport(unittest.TestCase):
    def test_removals_listed_with_counts_and_coordinates(self):
        blocks = {(0, 0, 0): "minecraft:stone"}
        for i in range(25):                                  # 25 floating lanterns, far from any support
            blocks[(10 + i * 3, 20, 0)] = "minecraft:lantern[hanging=false]"
        blocks[(0, 30, 5)] = "minecraft:torch"
        rep = placement.process(blocks, final=True, pack=None, version="1.21.1", check_ids=False)
        self.assertNotIn((10, 20, 0), blocks)
        self.assertNotIn((0, 30, 5), blocks)
        lan = [f for f in rep["fixed"] if "lantern" in f][0]
        self.assertIn("(×25)", lan)
        self.assertIn("(10, 20, 0)", lan)
        self.assertEqual(lan.count("(") - 1, 20 + 0)          # 20 coordinate tuples (plus the count marker)
        self.assertIn("5 more", lan)
        tor = [f for f in rep["fixed"] if "torch" in f][0]
        self.assertIn("(0, 30, 5)", tor)


if __name__ == "__main__":
    unittest.main()


class CheckerCrashIsReported(unittest.TestCase):
    def test_crash_in_block_check_reaches_problems(self):
        real = placement._check_block
        placement._check_block = lambda *a, **k: 1 / 0
        try:
            rep = placement.process({(0, 0, 0): "minecraft:stone"}, pack=None, version="1.21.1", check_ids=False)
        finally:
            placement._check_block = real
        self.assertTrue(any("crashed" in p and "ZeroDivisionError" in p for p in rep["problems"]))


class LightsKeptWithSupport(unittest.TestCase):
    def test_floating_lantern_gets_a_post_down_to_the_ground(self):
        blocks = {(x, 0, z): "minecraft:stone" for x in range(3) for z in range(3)}
        blocks[(1, 4, 1)] = "minecraft:lantern[hanging=false]"          # 3 blocks of air under it
        rep = placement.process(blocks, final=True, pack=None, version="1.21.1", check_ids=False)
        self.assertIn((1, 4, 1), blocks)                                  # the light stays
        self.assertTrue(all("fence" in blocks[(1, y, 1)] for y in (1, 2, 3)))
        self.assertTrue(any("fence post" in f for f in rep["fixed"]))

    def test_lantern_under_a_roof_hangs_from_a_chain(self):
        blocks = {(x, 6, z): "minecraft:stone" for x in range(3) for z in range(3)}
        blocks[(1, 3, 1)] = "minecraft:lantern[hanging=true]"            # roof 3 blocks above, nothing below
        placement.process(blocks, final=True, pack=None, version="1.21.1", check_ids=False)
        self.assertIn((1, 3, 1), blocks)
        self.assertTrue(all("chain" in blocks[(1, y, 1)] for y in (4, 5)))
