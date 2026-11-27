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
