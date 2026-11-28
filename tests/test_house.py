"""The house check (blockforge/house.py): proven houses pass, each kind of broken house fails with the right finding,
non-buildings give nothing, every path that runs checks.run gets it, and it stays fast."""
import time
import unittest

from tests import _env  # noqa: F401
from tests.test_bench_score import S, build
from blockforge import checks, examples, house, patterns as P, sandbox

SITE = "site(-14, -14, 22, 22, 0)\n"                              # grass top at y 0
SHELL = P.gable_roof_house_shell(0, 0, 8, 6, 0, 5, "white_terracotta", "spruce_stairs", "spruce")
# ^ foundation in the grass (floor y 0), door (4, 1, 6) facing south, lantern hanging at (4, 4, 3), plank ceiling at y 5


def framed(extra=""):
    """A 13 x 9 framed house (lit by framed_house), a door in the south wall and a gable roof."""
    return (P.framed_house(0, 0, 12, 8, 1, floors=1, storey=5) + P.doorway(6, 1, 8, "south")
            + P.gable_roof_trim(0, 0, 12, 8, 7) + extra)


DOOR = ("block(4, 1, 6, 'oak_door[facing=south,half=lower,hinge=left,open=false]')\n"
        "block(4, 2, 6, 'oak_door[facing=south,half=upper,hinge=left,open=false]')\n")
ATTIC = ("fill(0, 0, 0, 8, 0, 6, 'stone_bricks')\nwalls(0, 1, 0, 8, 4, 6, 'oak_planks')\n"   # a room, a ceiling at y 5,
         "fill(0, 5, 0, 8, 5, 6, 'spruce_planks')\nwalls(0, 6, 0, 8, 6, 6, 'oak_planks')\n"  # a 1-high attic, a flat roof
         "fill(0, 7, 0, 8, 7, 6, 'spruce_planks')\n" + DOOR + "block(4, 4, 3, 'lantern[hanging=true]')\n")
LADDER = "fill(2, 5, 1, 2, 5, 1, 'air')\n" + "".join(f"block(2, {y}, 1, 'ladder[facing=south]')\n" for y in range(1, 7))

# (name, script, kinds that must be found; empty = must pass with no house finding)
CALIBRATION = [
    ("cottage (gable house shell)", SITE + SHELL, set()),
    ("framed house + doorway + roof", SITE + framed(), set()),
    ("manor_layout", SITE + P.manor_layout(0, 1, 0), set()),
    ("manor_layout on stilts", SITE + P.manor_layout(0, 1, 0, stilts=True), set()),
    ("door one step up, with a stair step", SITE + P.gable_roof_house_shell(0, 0, 8, 6, 1, 5)
     + "block(4, 1, 7, 'oak_stairs[facing=north,half=bottom]')\n", set()),
    ("porch with steps", SITE + P.framed_house(0, 0, 10, 8, 3) + "fill(-1, 1, -1, 11, 1, 9, 'stone_bricks')\n"
     + P.porch(5, 3, 8, "south", steps=2) + P.gable_roof_trim(0, 0, 10, 8, 8), set()),
    ("sealed 1-high attic", SITE + ATTIC, set()),
    ("square spiral tower", SITE + P.square_spiral_stair(0, 0, 6, 1, 12), set()),
    ("door blocked by a block", SITE + SHELL + "fill(4, 1, 7, 4, 2, 7, 'stone_bricks')\n", {"door_unreachable"}),
    ("door 1 above the ground, no step", SITE + P.gable_roof_house_shell(0, 0, 8, 6, 1, 5), {"door_unreachable"}),
    ("interior split by a 2-high step", SITE + framed("fill(7, 1, 1, 11, 2, 7, 'spruce_planks')\n"),
     {"interior_unreachable"}),
    ("no light inside", SITE + SHELL + "block(4, 4, 3, 'air')\n", {"dark_spawn_spot"}),
    ("roof hole", SITE + SHELL + "fill(2, 5, 3, 2, 14, 3, 'air')\n", {"roof_hole"}),
    ("house floating 2 above the ground", SITE + P.gable_roof_house_shell(0, 0, 8, 6, 3, 5), {"wall_over_air"}),
    ("land piled 3 high against a wall", SITE + SHELL + "fill(-3, 1, 0, -1, 3, 6, 'dirt')\n", {"land_against_wall"}),
    ("1-high attic reached by a ladder", SITE + ATTIC + LADDER, {"low_headroom"}),
]

NOT_BUILDINGS = {
    "bridge": P.stone_arch_bridge(2, 6, 2, 11, 3),
    "trees": SITE + P.tree("oak", 0, 1, 0, 6) + P.tree("spruce", 6, 1, 6, 9),
    "hill": ("for x in range(-24, 25):\n  for z in range(-24, 25):\n    h = int(2 + 3 * noise(x, z, 9))\n"
             "    fill(x, 0, z, x, h, z, 'dirt')\n    block(x, h + 1, z, 'grass_block')\n"),
    "stilt deck": P.stilt_base(0, 0, 8, 6, 6),
    "pixel art": "fill(0, 0, 0, 20, 15, 0, 'red_wool')\nfill(5, 5, 0, 15, 10, 0, 'yellow_wool')\n",
    "hollow statue": "fill(0, 0, 0, 8, 12, 8, 'stone_bricks')\nfill(1, 1, 1, 7, 11, 7, 'air')\n",
    "plaza and lanterns": SITE + P.plaza(0, 0, 10, 10, 0) + P.lantern_post(-2, 1, -2),
    "fenced garden": SITE + P.fence_garden(0, 0, 10, 8, 1),
}


def kinds(blocks):
    return {f[0] for f in house.findings(blocks)}


class Calibration(unittest.TestCase):
    def test_good_houses_pass_and_broken_ones_fail_with_the_right_kind(self):
        for name, code, want in CALIBRATION:
            with self.subTest(name):
                got = kinds(sandbox.run_safe(code)[0])
                if want:
                    self.assertTrue(want <= got, f"{name}: want {sorted(want)}, got {sorted(got)}")
                else:
                    self.assertEqual(got, set(), name)

    def test_example_builds_pass(self):
        for name in examples.EXAMPLES:
            with self.subTest(name):
                self.assertEqual(house.findings(sandbox.run_safe(examples.code(name))[0]), [])

    def test_non_buildings_give_nothing(self):
        for name, code in NOT_BUILDINGS.items():
            with self.subTest(name):
                self.assertEqual(house.findings(sandbox.run_safe(code)[0]), [])


class Words(unittest.TestCase):
    """The findings say where and what to do, like the other checks."""

    def test_door_step_names_the_stair_and_its_facing(self):
        b, _ = sandbox.run_safe(SITE + P.gable_roof_house_shell(0, 0, 8, 6, 1, 5))
        f = [x for x in checks.run(b) if x["check"] == "door_unreachable"]
        self.assertEqual(len(f), 1)
        self.assertIn("1 block above the ground", f[0]["text"])
        self.assertIn("bottom stair facing north at (4, 1, 7)", f[0]["text"])
        self.assertEqual(f[0]["at"], [4, 2, 6])

    def test_dark_room_names_a_lantern_spot_and_gets_the_house_advice(self):
        b, _ = sandbox.run_safe(SITE + SHELL + "block(4, 4, 3, 'air')\n")
        found = checks.run(b)
        dark = [x for x in found if x["check"] == "dark_spawn_spot"]
        self.assertEqual(len(dark), 1)
        self.assertIn("block light 0", dark[0]["text"])
        self.assertIn("hang a lantern from the ceiling at", dark[0]["text"])
        self.assertIn(checks.HOUSE_ADVICE, checks.advice(found))
        self.assertIn("dark spawn spot 1", checks.summary(found))

    def test_every_kind_has_a_label(self):
        for k in checks.HOUSE_CHECKS:
            self.assertIn(k, checks.CHECK_LABELS)

    def test_split_room_names_the_step(self):
        b, _ = sandbox.run_safe(SITE + framed("fill(7, 1, 1, 11, 2, 7, 'spruce_planks')\n"))
        f = [x for x in checks.run(b) if x["check"] == "interior_unreachable"][0]
        self.assertRegex(f["text"], r"Only \d+% of the floor")
        self.assertIn("2-block step up", f["text"])

    def test_clean_house_adds_no_advice(self):
        found = checks.run(sandbox.run_safe(SITE + SHELL)[0])
        self.assertEqual([x for x in found if x["check"] in checks.HOUSE_CHECKS], [])
        self.assertNotIn(checks.HOUSE_ADVICE, checks.advice(found))


class Bench(unittest.TestCase):
    def test_bench_score_counts_house_problems(self):
        dark, _ = sandbox.run_safe(SITE + SHELL + "block(4, 4, 3, 'air')\n")
        lit, _ = sandbox.run_safe(SITE + SHELL)
        self.assertGreaterEqual(S.score(build(dark))["house"], 1)
        self.assertEqual(S.score(build(lit))["house"], 0)


class Speed(unittest.TestCase):
    @staticmethod
    def best(blocks, n=3):
        t = []
        for _ in range(n):
            t0 = time.perf_counter()
            house.findings(blocks)
            t.append(time.perf_counter() - t0)
        return min(t)

    def test_a_60_x_40_x_60_house_takes_under_half_a_second(self):
        b, _ = sandbox.run_safe(P.framed_house(0, 0, 59, 59, 1, floors=7, storey=4) + P.doorway(30, 1, 59, "south"))
        self.assertGreaterEqual(max(p[0] for p in b) - min(p[0] for p in b), 59)
        self.assertLess(self.best(b), 0.5)

    def test_a_200_x_200_town_takes_under_5_seconds(self):
        town = "site(0, 0, 199, 199, 0)\nfill(0, -4, 0, 199, -1, 199, 'dirt')\n" + "".join(
            P.gable_roof_house_shell(8 + 24 * i, 8 + 24 * j, 18 + 24 * i, 16 + 24 * j, 0, 5)
            for i in range(8) for j in range(8))
        b, _ = sandbox.run_safe(town)
        self.assertEqual(house.findings(b), [])
        self.assertLess(self.best(b, 2), 5.0)


if __name__ == "__main__":
    unittest.main()
