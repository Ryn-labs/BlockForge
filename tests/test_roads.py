"""Streets that are never buried (round 5: the 1.15 hill town had 16 path cells with ground or stone right on top of
them). road() clears the room above every cell, fills under it and follows the ground or the plan_layout heights;
the checks find a covered path with its exact cell, like the bench scorer, and the improvement message lists them."""
import os
import sys
import unittest

from tests import _env  # noqa: F401
from tests.test_bench_score import build
from blockforge import checks, layout, patterns, sandbox, selfimprove, terrain

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench"))
import score as S  # noqa: E402

_land = {}


def mountain():
    if "m" not in _land:
        _land["m"] = sandbox.run_safe("natural_terrain(0, 0, 95, 95, y=0, height=30, kind='mountain', seed=4)\n")[0]
    return _land["m"]


def bench(blocks):
    return S.score(build({p: s.replace("minecraft:", "") for p, s in blocks.items()}))


class PlannedTown(unittest.TestCase):
    """A synthetic mountain, a plan_layout town on it and its streets laid with the line plan_layout prints."""

    @classmethod
    def setUpClass(cls):
        land = mountain()
        top = terrain.ground_top(land, land)
        parts = ([{"name": f"h{i}", "w": 9, "l": 9, "kind": "house"} for i in range(5)]
                 + [{"name": "square", "w": 11, "l": 11, "kind": "plaza"}])
        cls.plan = layout.plan(top, [8, 8, 88, 88], parts, 3)
        code = []
        for r in cls.plan["parts"]:                                   # terraces: cut above, fill below, then the house
            lv = r["level"]
            code.append(f"fill({r['x1']}, {lv + 1}, {r['z1']}, {r['x2']}, {lv + 40}, {r['z2']}, 'air')")
            code.append(f"fill({r['x1']}, {lv - 8}, {r['z1']}, {r['x2']}, {lv}, {r['z2']}, 'dirt')")
            code.append(patterns.framed_house(r["x1"] + 1, r["z1"] + 1, r["x2"] - 1, r["z2"] - 1, lv + 1)
                        if r["kind"] == "house" else patterns.plaza(r["x1"], r["z1"], r["x2"], r["z2"], lv, well=False))
        cls.houses = sandbox.run_safe("\n".join(code), base=(land, {}))[0]
        cls.text = layout.plan_text(cls.plan)
        streets = [line.split("lay it with: ", 1)[1] for line in cls.text.splitlines() if "lay it with: " in line]
        cls.streets = streets
        cls.town = sandbox.run_safe("\n".join(streets), base=(cls.houses, {}))[0]

    def test_plan_prints_a_road_line_per_street(self):
        self.assertEqual(len(self.streets), len(self.plan["streets"]))
        self.assertTrue(all(s.startswith("road([[") for s in self.streets))

    def test_no_buried_path_cells(self):
        r = bench(self.town)
        self.assertEqual(r["buried_path"], 0)
        self.assertEqual(r["floating"], bench(self.houses)["floating"])         # the cuts leave nothing hanging
        self.assertEqual([f for f in checks.run(self.town) if f["check"] in ("buried_path", "headroom")], [])

    def test_streets_have_room_above_and_ground_below(self):
        cols = {}
        for (x, y, z), st in self.town.items():
            if "dirt_path" in st or "cobblestone_slab" in st:
                cols.setdefault((x, z), []).append(y)
        for s in self.plan["streets"]:
            for x, z, y in s["cells"][::3]:
                ys = cols.get((x, z))
                self.assertTrue(ys, (x, z))
                top = max(ys)
                self.assertLessEqual(abs(top - y), 2, (x, z))                    # at the planned height
                for h in (1, 2, 3):
                    self.assertIsNone(self.town.get((x, top + h, z)), (x, top + h, z))
                self.assertIsNotNone(self.town.get((x, top - 1, z)))


class GroundRoad(unittest.TestCase):
    def test_road_follows_the_ground_over_a_mountain(self):
        land = mountain()
        b = sandbox.run_safe(patterns.road([[10, 48], [50, 48], [50, 85], [85, 85]], width=3), base=(land, {}))[0]
        r = bench(b)
        for k in ("buried_path", "jump_steps", "floating"):
            self.assertEqual(r[k], 0, k)
        ys = [y for (x, y, z), s in b.items() if (x, z) == (30, 48) and ("dirt_path" in s or "slab" in s)]
        top = terrain.ground_top(land, land)[(30, 48)]
        self.assertEqual(len(ys), 1)
        self.assertLessEqual(abs(ys[0] - top), 3)                            # on the ground, not a level line in the air

    def test_stair_run_into_a_slope_is_cleared(self):
        code = "fill(0, 0, 0, 12, 8, 6, 'stone')\n" + patterns.straight_stair_run(2, 3, 2, "east", 4, width=2)
        b = sandbox.run_safe(code)[0]
        self.assertEqual([f for f in checks.run(b) if f["check"] in ("buried_path", "headroom")], [])
        self.assertEqual(bench(b)["buried_path"], 0)


class CoveredPathCheck(unittest.TestCase):
    def street(self, cover):
        b = {(x, 0, z): "minecraft:stone" for x in range(16) for z in range(5)}
        for x in range(16):
            for z in (1, 2, 3):
                b[(x, 1, z)] = "minecraft:stone_bricks"
        for x in range(6, 9):
            for z in (1, 2, 3):
                b[(x, 2, z)] = "minecraft:" + cover                           # a bank of ground over the street
        return b

    def test_ground_over_a_street_is_found_at_its_cells(self):
        b = self.street("andesite")
        found = [f for f in checks.run(b) if f["check"] == "buried_path"]
        self.assertEqual(sorted(tuple(f["at"]) for f in found), sorted((x, 1, z) for x in range(6, 9) for z in (1, 2, 3)))
        self.assertIn("has andesite on top of it at (6, 2, 1)", " ".join(f["text"] for f in found))
        self.assertEqual(len(found), bench(b)["buried_path"])                 # the same cells as the bench
        self.assertIn(checks.BURIED_ADVICE, checks.advice(found))

    def test_improve_message_lists_every_cell(self):
        a = selfimprove.assess(self.street("dirt"), with_quality=False)
        msg = selfimprove.improve_message(a, 1, 2)
        self.assertIn("all cells: ", msg)
        for x in range(6, 9):
            for z in (1, 2, 3):
                self.assertIn(f"({x}, 1, {z})", msg)
        self.assertIn("road(points", msg)

    def test_a_house_floor_is_not_a_buried_street(self):
        b = self.street("oak_planks")
        self.assertEqual([f for f in checks.run(b) if f["check"] == "buried_path"], [])


class ShortStreets(unittest.TestCase):
    def test_two_close_entrances_are_joined_straight(self):
        top = {(x, z): 4 for x in range(60) for z in range(60)}
        parts = [{"name": "a", "w": 9, "l": 9, "kind": "plaza"}, {"name": "b", "w": 9, "l": 9, "kind": "house", "near": "a"}]
        plan = layout.plan(top, [0, 0, 59, 59], parts, 3)
        for s in plan["streets"]:
            (x1, z1, _), (x2, z2, _) = s["cells"][0], s["cells"][-1]
            self.assertLessEqual(s["length"], abs(x2 - x1) + abs(z2 - z1) + 3)      # no loop round to reach the goal


if __name__ == "__main__":
    unittest.main()
