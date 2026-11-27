import unittest

from tests import _env  # noqa: F401
from blockforge import buildkit as bk


def reset():
    bk._blocks.clear()
    bk._meta.pop("overwrites", None)
    if hasattr(bk, "_reset_overwrites"):
        bk._reset_overwrites()


class FillOutline(unittest.TestCase):
    def setUp(self):
        reset()

    def test_outline_one_high_draws_only_rim(self):
        bk.fill(0, 0, 0, 4, 0, 4, "stone", outline=True)
        self.assertEqual(len(bk._blocks), 16)
        self.assertNotIn((2, 0, 2), bk._blocks)
        self.assertIn((0, 0, 2), bk._blocks)

    def test_outline_tall_box_unchanged(self):
        bk.fill(0, 0, 0, 4, 2, 4, "stone", outline=True)
        self.assertEqual(len(bk._blocks), 66)           # shell of a 5x3x5 box: 2 faces + ring
        self.assertNotIn((2, 1, 2), bk._blocks)

    def test_hollow_one_high_unchanged(self):
        bk.fill(0, 0, 0, 4, 0, 4, "stone", hollow=True)
        self.assertEqual(len(bk._blocks), 25)


if __name__ == "__main__":
    unittest.main()


class Overwrites(unittest.TestCase):
    def setUp(self):
        reset()

    def test_same_block_air_and_new_are_not_counted(self):
        bk.block(0, 0, 0, "stone")
        bk.block(0, 0, 0, "minecraft:stone")             # same block
        bk.block(1, 0, 0, "stone")
        bk.block(1, 0, 0, "air")                         # removal
        bk.block(1, 0, 0, "dirt")                        # onto empty
        self.assertEqual(bk.overwrites()["count"], 0)

    def test_different_block_counted_last_write_wins(self):
        bk.block(0, 0, 0, "stone")
        bk.block(0, 0, 0, "dirt")
        ow = bk.overwrites()
        self.assertEqual(ow["count"], 1)
        self.assertEqual(ow["examples"][0]["at"], [0, 0, 0])
        self.assertEqual(bk.get(0, 0, 0), "minecraft:dirt")

    def test_examples_capped_at_20(self):
        bk.fill(0, 0, 0, 9, 9, 0, "stone")
        bk.fill(0, 0, 0, 9, 9, 0, "dirt")
        ow = bk.overwrites()
        self.assertEqual(ow["count"], 100)
        self.assertEqual(len(ow["examples"]), 20)

    def test_replace_is_deliberate(self):
        bk.fill(0, 0, 0, 3, 0, 0, "stone")
        bk.replace(0, 0, 0, 3, 0, 0, "stone", "dirt")
        self.assertEqual(bk.overwrites()["count"], 0)
        self.assertEqual(bk.get(2, 0, 0), "minecraft:dirt")

    def test_base_blocks_not_counted_once(self):
        bk._blocks[(0, 0, 0)] = "minecraft:stone"
        bk._ow_skip.add((0, 0, 0))
        bk.block(0, 0, 0, "dirt")
        self.assertEqual(bk.overwrites()["count"], 0)
        bk.block(0, 0, 0, "glass")
        self.assertEqual(bk.overwrites()["count"], 1)
