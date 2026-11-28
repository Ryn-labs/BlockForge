import json
import math
import os
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
        self.assertLessEqual(info["peak_y"], 2 + 50 + 4)
        snow = [p for p, s in b.items() if s == tg.SNOW]
        self.assertTrue(snow)
        self.assertTrue(all(p[1] >= info["snowline"] - tg.LEDGE_SNOW for p in snow))   # ledges hold snow a bit lower
        self.assertGreater(sum(1 for p in snow if p[1] >= info["snowline"] - 4) / len(snow), 0.9)
        clean, cinfo = tg.generate(96, 96, "mountain", 50, seed=3, snow_mix=0)          # snow_mix 0: the old clean cap
        self.assertTrue(all(p[1] >= cinfo["snowline"] - 4 for p, s in clean.items() if s == tg.SNOW))

    def test_snow_and_dark_rock_mix_on_the_high_ground(self):
        b, info = self.mountain
        high = [st for (y, st) in tq.surface(b).values() if y >= info["snowline"]]
        snow = sum(1 for st in high if st == tg.SNOW)
        dark = sum(1 for st in high if st in ("minecraft:deepslate", "minecraft:tuff", "minecraft:cobbled_deepslate"))
        self.assertGreater(snow / len(high), 0.3)
        self.assertGreater(dark / len(high), 0.08)                  # dark rock shows through, not a clean white cap

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

    def test_same_seed_same_mountain_every_knob(self):
        args = dict(seed=5, ruggedness=0.8, ledges=0.4, snow_mix=0.9)
        b, info = tg.generate(56, 48, "mountain", 30, **args)
        self.assertEqual(b, tg.generate(56, 48, "mountain", 30, **args)[0])
        self.assertNotEqual(b, tg.generate(56, 48, "mountain", 30, **dict(args, seed=6))[0])
        self.assertNotEqual(b, tg.generate(56, 48, "mountain", 30, **dict(args, ledges=0.9))[0])
        self.assertEqual((info["ruggedness"], info["ledges"], info["snow_mix"]), (0.8, 0.4, 0.9))
        self.assertEqual(tg.generate(40, 40, "range", 20, seed=1)[1]["ruggedness"], tg.RUGGED)   # default = new look


class NoFlatCutTest(unittest.TestCase):
    """No accidental cut edges: no wall over 3 blocks except on marked cliffs, no long straight step lines, no flat
    plate at the top, and the land comes down to the ground at every side of the box."""

    CASES = ((80, 80, "mountain", 55, 0), (96, 96, "mountain", 50, 3), (90, 80, "range", 40, 2),
             (110, 70, "valley", 40, 3), (90, 80, "hills", 40, 2), (60, 40, "mountain", 30, 7))

    def test_walls_only_on_marked_cliffs(self):
        for w, l, kind, height, seed in self.CASES:
            h, river, _, cliff = tg.heightmap(w, l, kind, height, seed, 3)
            top = [[int(round(v)) for v in row] for row in h]
            bad = [(x, z) for z in range(l) for x in range(w) for nx, nz in ((x + 1, z), (x, z + 1))
                   if nx < w and nz < l and abs(top[z][x] - top[nz][nx]) > 3 and not (cliff[z][x] or cliff[nz][nx])
                   and (x, z) not in river and (nx, nz) not in river]
            self.assertEqual(bad, [], (kind, seed))
            walls = sum(1 for z in range(l) for x in range(w) for nx, nz in ((x + 1, z), (x, z + 1))
                        if nx < w and nz < l and abs(top[z][x] - top[nz][nx]) > 3)
            self.assertLess(walls / (2 * w * l), 0.015, (kind, seed))   # real cliffs are the exception, not the mountain

    def test_no_long_straight_step_lines(self):
        for w, l, kind, height, seed in self.CASES:
            h = tg.heightmap(w, l, kind, height, seed, 3)[0]
            top = [[int(round(v)) for v in row] for row in h]
            lines = [[top[z][x] for x in range(w)] for z in range(l)] + [[top[z][x] for z in range(l)] for x in range(w)]
            longest = 0
            for line in lines:
                run, last = 0, 0
                for a, b in zip(line, line[1:]):
                    d = b - a
                    run = run + 1 if d and d == last else (1 if d else 0)
                    last = d
                    longest = max(longest, run)
            self.assertLessEqual(longest, 18, (kind, seed))            # the same step 18+ times in a row: a ramp

    def test_no_flat_top_and_edges_meet_the_ground(self):
        for w, l, kind, height, seed in self.CASES:
            b, info = tg.generate(w, l, kind, height, seed=seed, trees=False, boulders=False)
            q = tq.score(b)
            self.assertLess(q["top_plate"], 0.05, (kind, seed))
            self.assertLess(q["edge_walls"], 0.05, (kind, seed))
            h = _top(b)
            border = [y for (x, z), y in h.items() if x in (0, w - 1) or z in (0, l - 1)]
            self.assertLess(sum(border) / len(border), 2 + 0.15 * height, (kind, seed))


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
            self.assertLess(q["total"], 50, (name, q))
            self.assertTrue(q["notes"], name)

    def test_a_house_is_not_terrain(self):
        b = self._bad(lambda: (bk.walls(40, 3, 40, 60, 12, 60, "oak_planks"), bk.fill(40, 12, 40, 60, 12, 60, "spruce_planks")))
        small = {p: s for p, s in b.items() if 30 <= p[0] <= 70 and 30 <= p[2] <= 70}
        self.assertFalse(tq.is_terrain(small))


def _columns(top, w, l):
    b = {}
    for z in range(l):
        for x in range(w):
            y, st = top(x, z)
            for yy in range(y + 1):
                b[(x, yy, z)] = st if yy == y else "minecraft:stone"
    return b


class TooPerfectTest(unittest.TestCase):
    """Calibration of the 'too perfect' parts (round 2 mountains): the 1.15 bench snowy mountain (even slopes, one
    sharp top, a clean white cap) drops below 75, the new default mountain for the same prompt scores 85+, and fakes
    with flat cuts or a cone shape stay under 50."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(__file__), "data", "bench_snowy_mountain_115_surface.json")) as f:
            d = json.load(f)
        pal, cols, old = d["palette"], d["cols"], {}
        for i in range(0, len(cols), 5):
            x, z, y, t, a = cols[i:i + 5]
            old[(x, y, z)] = pal[t]
            if a >= 0:
                old[(x, y + 1, z)] = pal[a]
        cls.old_115 = old
        # the bench prompt: natural_terrain(kind='mountain', x1=0, z1=0, x2=79, z2=79, y=2, height=55)
        cls.new = [tg.generate(80, 80, "mountain", 55, seed=s, base=3)[0] for s in (0, 1)]
        cls.smooth = tg.generate(80, 80, "mountain", 55, seed=0, base=3, ruggedness=0, ledges=0, snow_mix=0)[0]

    def test_the_115_snowy_mountain_is_too_perfect(self):
        q = tq.score(self.old_115)
        self.assertTrue(q["terrain"])
        self.assertLess(q["total"], 75, q)
        self.assertLess(q["parts"]["slopes"], tq.PARTS["slopes"] - 5, q)       # even slopes
        self.assertLess(q["parts"]["snow"], tq.PARTS["snow"] - 10, q)          # a clean white cap
        self.assertTrue(any("clean cap" in n for n in q["notes"]), q["notes"])

    def test_the_smooth_116_look_scores_below_the_new_default(self):
        old, new = tq.score(self.smooth), tq.score(self.new[0])
        self.assertLess(old["total"], 75, old)
        self.assertGreaterEqual(new["total"] - old["total"], 12, (old["total"], new["total"]))

    def test_new_default_mountain_scores_85_plus(self):
        for b in self.new:
            q = tq.score(b)
            self.assertGreaterEqual(q["total"], 85, q)
            self.assertGreaterEqual(q["slope_rhythm"], 1.0, q)
            self.assertLess(q["snow_cap"], 0.8, q)

    def test_flat_cut_and_cone_fakes_score_under_50(self):
        h = tg.heightmap(90, 90, "mountain", 50, 5, 3, None, 0, 0)[0]
        cap = 3 + 50 * 0.55
        clamped = _columns(lambda x, z: (int(round(min(h[z][x], cap))), "minecraft:stone"), 90, 90)
        big, _ = tg.generate(140, 140, "mountain", 55, seed=4, trees=False)
        cropped = {(x - 45, y, z - 30): s for (x, y, z), s in big.items() if 45 <= x < 125 and 30 <= z < 110}

        def snowcone(x, z):
            y = int(round(max(3, 50 - math.hypot(x - 40, z - 40) * 1.4)))
            return y, ("minecraft:snow_block" if y > 38 else "minecraft:grass_block")
        cone = _columns(snowcone, 80, 80)
        for name, b in (("clamped top", clamped), ("cut at the box", cropped), ("snow cone", cone)):
            self.assertLess(tq.score(b)["total"], 50, (name, tq.score(b)))
        self.assertTrue(any("cut flat" in n for n in tq.score(clamped)["notes"]))
        self.assertTrue(any("box edge" in n for n in tq.score(cropped)["notes"]))
        self.assertTrue(any("cone" in n for n in tq.score(cone)["notes"]))


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
        smooth = session.start("smooth hill", "80 x 80 mountain", None)
        text2, err = _call("make_terrain", {"session": smooth.id, "kind": "mountain", "x1": 0, "z1": 0, "x2": 79, "z2": 79,
                                            "height": 36, "seed": 4, "ruggedness": 0, "ledges": 0, "snow_mix": 0})
        self.assertFalse(err, text2)
        self.assertNotEqual(session.load(smooth.id).blocks, session.load(s.id).blocks)   # the knobs reach the generator
        bad = session.start("cone", "80 x 80 mountain", None)
        session.step(bad, "fill(0, 0, 0, 79, 2, 79, 'grass_block')\ncone(40, 3, 40, 34, 40, 'stone')")
        text, err = _call("save_build", {"session": bad.id, "accept_problems": "test"})
        self.assertTrue(err)
        self.assertIn("terrain", text.lower())


if __name__ == "__main__":
    unittest.main()
