import unittest

from tests import _env  # noqa: F401
from blockforge import buildkit as bk, mcp_server, session, terrain_gen as tg, terrain_quality as tq


def _call(name, args):
    out = mcp_server.handle({"method": "tools/call", "id": 1, "params": {"name": name, "arguments": args}})
    return out["content"][0]["text"], bool(out.get("isError"))


def _top(blocks):
    top = tq.surface(blocks)
    return {c: v[0] for c, v in top.items()}


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mountain = tg.generate(96, 96, "mountain", 50, seed=3)
        cls.valley = tg.generate(110, 70, "valley", 40, seed=3)

    def test_same_arguments_same_blocks(self):
        b, _ = tg.generate(40, 40, "hills", 12, seed=8)
        self.assertEqual(b, tg.generate(40, 40, "hills", 12, seed=8)[0])
        self.assertNotEqual(b, tg.generate(40, 40, "hills", 12, seed=9)[0])

    def test_reaches_the_height_and_snows_on_top(self):
        b, info = self.mountain
        self.assertGreaterEqual(info["peak_y"], 2 + 50 - 4)
        snow = [p for p, s in b.items() if s == tg.SNOW]
        self.assertTrue(snow)
        self.assertTrue(all(p[1] >= info["snowline"] - 4 for p in snow))

    def test_slopes_step_at_most_three_outside_cliffs(self):
        h = _top(self.mountain[0])
        big = sum(1 for (x, z), y in h.items() for o in (h.get((x + 1, z)), h.get((x, z + 1))) if o is not None and abs(o - y) > 3)
        self.assertLess(big / len(h), 0.02)

    def test_edges_are_low_rolling_land(self):
        h = _top(self.mountain[0])
        border = [y for (x, z), y in h.items() if x in (0, 95) or z in (0, 95)]
        self.assertLess(max(border), 2 + 0.12 * 50)
        self.assertGreater(len(set(border)), 1)                     # not one flat rim

    def test_valley_has_water_below_its_banks(self):
        b, info = self.valley
        water = [p for p, s in b.items() if s == tg.WATER]
        self.assertTrue(water)
        self.assertTrue(all(p[1] <= info["water_y"] for p in water))

    def test_kind_is_checked(self):
        with self.assertRaises(ValueError):
            tg.generate(30, 30, "volcano", 20)


class ScoreTest(unittest.TestCase):
    def _bad(self, fn):
        bk._blocks.clear()
        bk.fill(0, 0, 0, 99, 2, 99, "grass_block")
        fn()
        return dict(bk._blocks)

    def test_generated_land_scores_high(self):
        for kind in ("mountain", "range", "valley", "hills"):
            b, _ = tg.generate(90, 80, kind, 40, seed=2)
            q = tq.score(b)
            self.assertTrue(q["terrain"], kind)
            self.assertGreaterEqual(q["total"], 80, (kind, q))

    def test_cone_and_stacked_boxes_score_low(self):
        cone = self._bad(lambda: bk.cone(50, 3, 50, 40, 45, "stone"))
        boxes = self._bad(lambda: [bk.fill(8 + k * 5, 3, 8 + k * 5, 91 - k * 5, 3 + (k + 1) * 5, 91 - k * 5, "grass_block") for k in range(7)])
        for name, b in (("cone", cone), ("boxes", boxes)):
            q = tq.score(b)
            self.assertLess(q["total"], tq.TERRAIN_MIN, (name, q))
            self.assertTrue(q["notes"], name)

    def test_a_house_is_not_terrain(self):
        b = self._bad(lambda: (bk.walls(40, 3, 40, 60, 12, 60, "oak_planks"), bk.fill(40, 12, 40, 60, 12, 60, "spruce_planks")))
        small = {p: s for p, s in b.items() if 30 <= p[0] <= 70 and 30 <= p[2] <= 70}
        self.assertFalse(tq.is_terrain(small))


class ToolTest(unittest.TestCase):
    def test_buildkit_helper_places_land_at_y(self):
        bk._blocks.clear()
        info = bk.natural_terrain(10, 20, 69, 79, y=64, height=30, kind="hills", seed=1, trees=False)
        xs = [p[0] for p in bk._blocks]
        zs = [p[2] for p in bk._blocks]
        self.assertEqual((min(xs), max(xs), min(zs), max(zs)), (10, 69, 20, 79))
        self.assertGreater(info["peak_y"], 64)

    def test_make_terrain_tool_and_save_gate(self):
        s = session.start("hill test", "80 x 80 mountain", None)
        text, err = _call("make_terrain", {"session": s.id, "kind": "mountain", "x1": 0, "z1": 0, "x2": 79, "z2": 79,
                                           "height": 36, "seed": 4})
        self.assertFalse(err, text)
        self.assertIn("Terrain: terrain", text)
        bad = session.start("cone", "80 x 80 mountain", None)
        session.step(bad, "fill(0, 0, 0, 79, 2, 79, 'grass_block')\ncone(40, 3, 40, 34, 40, 'stone')")
        text, err = _call("save_build", {"session": bad.id, "accept_problems": "test"})
        self.assertTrue(err)
        self.assertIn("terrain", text.lower())


if __name__ == "__main__":
    unittest.main()
