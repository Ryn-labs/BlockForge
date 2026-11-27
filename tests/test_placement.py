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
