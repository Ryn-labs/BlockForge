import math
import os
import tempfile
import time
import unittest

from tests import _env  # noqa: F401
from blockforge import checks, exporters, layout, mcp_server, session, store, terrain


def hill_blocks(n=40, peak=14):
    """A smooth grass hill on stone: x, z in 0..n-1, bottom at y 0."""
    b = {}
    for x in range(n):
        for z in range(n):
            h = 4 + int(peak * math.exp(-(((x - n * 0.6) ** 2 + (z - n * 0.4) ** 2) / (2 * (n / 5) ** 2))))
            for y in range(h + 1):
                b[(x, y, z)] = "minecraft:grass_block" if y == h else ("minecraft:dirt" if y > h - 3 else "minecraft:stone")
    return b


def hill_file(n=40):
    d = tempfile.mkdtemp(prefix="bf_hill_")
    path = os.path.join(d, "hill.schem")
    exporters.write_schem(path, exporters.to_dict(hill_blocks(n)), "hill")
    return path


def call(name, args, n=1):
    return mcp_server.handle({"method": "tools/call", "id": n, "params": {"name": name, "arguments": args}})


class TerrainSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = hill_file()

    def test_start_from_file_and_build_id(self):
        s = session.start("On a hill", "small", terrain=self.path)
        self.assertEqual(len(s.blocks), len(hill_blocks()))
        self.assertEqual(s.terrain, set(s.blocks))
        s2 = session.load(s.id)                                   # survives a restart, terrain kept separately
        self.assertEqual(s2.terrain, s.terrain)
        self.assertEqual(s2.terrain_top, s.terrain_top)
        self.assertTrue(os.path.exists(os.path.join(session.DIR, s.id + ".terrain.json")))
        m = store.save_build(dict(s.blocks), "site", source="import")
        s3 = session.start("From id", terrain=m["id"])
        self.assertEqual(len(s3.terrain), len(s.terrain))
        with self.assertRaises(session.SessionError):
            session.start("bad", terrain="no-such-thing")

    def test_terrain_change_counting(self):
        s = session.start("Count", terrain=self.path)
        top = min(s.terrain_top[(x, z)] for x in range(8, 12) for z in range(8, 12))
        r = session.step(s, f"fill(8,{top - 1},8,11,{top},11,'air')\n", "dig")
        self.assertIn("Terrain: dug 32 blocks, replaced 0, filled 0.", r)
        r = session.step(s, f"fill(8,{top - 1},8,9,{top - 1},9,'stone_bricks')\nfill(8,{top + 1},8,9,{top + 3},9,'oak_planks')\n", "fill+build")
        self.assertIn("filled 4", r)
        self.assertIn("In all so far: dug 32", r)
        t2 = min(s.terrain_top[(x, z)] for x in range(20, 22) for z in range(20, 22))
        r = session.step(s, f"fill(20,{t2},20,21,{t2},21,'cobblestone')\n")
        self.assertIn("replaced 4", r)
        self.assertNotIn("overwritten", r)                        # swapping land is reported as terrain, not as an overwrite
        s = session.load(s.id)
        self.assertEqual(session.terrain_total(s), {"dug": 32, "replaced": 4, "filled": 4})
        session.undo(s, 1)
        self.assertEqual(session.terrain_total(s)["replaced"], 0)
        self.assertIn("dug 32", session.describe_text(s))

    def test_ground_text(self):
        s = session.start("Ground", terrain=self.path)
        rows = session.ground_text(s, 0, 0, 5, 3).splitlines()
        self.assertEqual(len(rows), 2 + 4)
        self.assertEqual(rows[2].split()[1:], [str(s.terrain_top[(x, 0)]) for x in range(6)])
        self.assertEqual(len(session.ground_text(s).splitlines()), 2 + 40)
        s2 = session.start("Big")
        session.step(s2, "fill(0,0,0,199,0,199,'stone')\n")
        t = session.ground_text(s2)
        self.assertIn("every 4 blocks", t)
        self.assertLessEqual(max(len(r.split()) for r in t.splitlines()[1:]), 65)
        self.assertIn("highest", session.describe_text(session.start("d", terrain=self.path)))

    def test_trees_are_not_ground(self):
        b = hill_blocks(8, 2)
        top = max(y for (x, y, z) in b if (x, z) == (3, 3))
        for y in range(top + 1, top + 5):
            b[(3, y, 3)] = "minecraft:oak_log"
        b[(3, top + 5, 3)] = "minecraft:oak_leaves"
        self.assertEqual(terrain.ground_top(b, b)[(3, 3)], top)

    def test_floating_and_buried_checks_use_the_land(self):
        s = session.start("Checks", terrain=self.path)
        t = s.terrain_top[(2, 2)]
        ok = session.step(s, f"fill(2,{t + 1},2,5,{t + 4},5,'oak_planks', hollow=True)\n")
        self.assertIn("Checks: no problems found", ok)
        y = max(s.terrain_top.values()) + 6
        r = session.step(s, f"fill(30,{y},30,32,{y + 2},32,'stone_bricks')\n")
        self.assertIn("floating parts 1", r)
        self.assertIn("above the ground", r)
        # a gravel path that runs into the hill flank
        s = session.start("Buried", terrain=self.path)
        ty = s.terrain_top[(24, 16)]
        r = session.step(s, f"fill(24,{ty - 3},12,24,{ty - 3},20,'gravel')\n")
        self.assertIn("buried path", r)
        self.assertTrue(any(f["check"] == "buried_path" for f in checks.run(s.blocks, ground=s.ground())))

    def test_natural_terrain_has_no_findings(self):
        s = session.start("Clean", terrain=self.path)
        self.assertEqual(checks.run(s.blocks, ground=s.ground()), [])

    def test_mcp_start_with_terrain(self):
        text = call("start_build", {"title": "T", "terrain": self.path})["content"][0]["text"]
        self.assertIn("on terrain", text)
        sid = text.split()[2]
        g = call("ground", {"session": sid, "x1": 0, "z1": 0, "x2": 3, "z2": 1}, 2)
        self.assertIn("Ground height", g["content"][0]["text"])


class ParallelParts(unittest.TestCase):
    def test_parts_merge_and_conflict(self):
        s = session.start("Parts")
        session.step(s, "fill(0,0,0,30,0,10,'stone')\n", "floor")
        parts = [{"note": "house a", "code": "fill(0,1,0,4,3,4,'oak_planks', hollow=True)\n"},
                 {"note": "house b", "code": "fill(10,1,0,14,3,4,'spruce_planks', hollow=True)\n"},
                 {"note": "clash", "code": "fill(4,1,0,7,3,4,'bricks', hollow=True)\n"}]
        r = session.step_parts(s, parts, "street")
        self.assertIn("Ran 3 of 3 parts", r)
        self.assertIn("Conflict: part 3 (clash)", r)
        self.assertEqual(s.blocks[(4, 2, 0)], "minecraft:oak_planks")          # the first part kept the shared edge
        self.assertEqual(s.blocks[(7, 2, 0)], "minecraft:bricks")
        self.assertEqual(s.blocks[(12, 1, 0)], "minecraft:spruce_planks")
        self.assertEqual(len(s.history), 2)
        self.assertEqual(len(session.load(s.id).history), 2)
        session.undo(s, 1)
        self.assertNotIn((7, 2, 0), s.blocks)

    def test_failed_part_is_skipped(self):
        s = session.start("Parts2")
        r = session.step_parts(s, [{"code": "fill(0,0,0,2,0,2,'stone')\n"}, {"code": "this is not python ("}])
        self.assertIn("failed and was skipped", r)
        self.assertEqual(len(s.blocks), 9)
        with self.assertRaises(session.SessionError):
            session.step_parts(s, [{"code": "this is not python ("}])

    def test_mcp_build_step_parts(self):
        sid = call("start_build", {"title": "P"})["content"][0]["text"].split()[2]
        r = call("build_step", {"session": sid, "parts": [{"code": "fill(0,0,0,2,0,2,'stone')\n"},
                                                          {"code": "fill(5,0,0,7,0,2,'stone')\n"}]}, 2)
        self.assertIn("Ran 2 of 2 parts", r["content"][0]["text"])


class PlanLayout(unittest.TestCase):
    def setUp(self):
        n = 160
        self.top = {(x, z): int(8 + 18 * math.exp(-(((x - n * 0.6) ** 2 + (z - n * 0.4) ** 2) / (2 * (n / 5) ** 2)))
                                + 3 * math.sin(x / 9) * math.cos(z / 11)) for x in range(n) for z in range(n)}
        self.parts = ([{"name": "castle", "w": 24, "l": 24, "kind": "castle"}, {"name": "plaza", "w": 16, "l": 12, "kind": "plaza"},
                       {"name": "shrine", "w": 8, "l": 8, "kind": "shrine"}]
                      + [{"name": f"h{i}", "w": 9 + i % 3, "l": 8, "kind": "house", "near": "plaza"} for i in range(8)])
        self.plan = layout.plan(self.top, [0, 0, 159, 159], self.parts, 5)

    def test_no_overlap_and_gap(self):
        rs = self.plan["parts"]
        self.assertEqual(len(rs), 11)
        for i, a in enumerate(rs):
            self.assertTrue(0 <= a["x1"] and a["x2"] <= 159 and 0 <= a["z1"] and a["z2"] <= 159)
            for b in rs[i + 1:]:
                gap_x = max(b["x1"] - a["x2"], a["x1"] - b["x2"]) - 1
                gap_z = max(b["z1"] - a["z2"], a["z1"] - b["z2"]) - 1
                self.assertGreaterEqual(max(gap_x, gap_z), 3, (a["name"], b["name"]))

    def test_castle_on_the_high_ground_and_flat_spots(self):
        castle = next(r for r in self.plan["parts"] if r["name"] == "castle")
        self.assertGreaterEqual(castle["level"], max(self.top.values()) - 8)
        for r in self.plan["parts"]:
            self.assertLessEqual(r["max_dev"], 5, r["name"])

    def test_streets_connect_everything_and_obey_the_slope(self):
        parts = {r["name"]: r for r in self.plan["parts"]}
        adj = {n: set() for n in parts}
        for s in self.plan["streets"]:
            adj[s["from"]].add(s["to"])
            adj[s["to"]].add(s["from"])
            cells = s["cells"]
            for (x1, z1, y1), (x2, z2, y2) in zip(cells, cells[1:]):
                self.assertEqual(abs(x2 - x1) + abs(z2 - z1), 1)               # a connected line of cells
            for i in range(len(cells)):
                for j in range(max(0, i - 8), i):
                    self.assertLessEqual(abs(cells[i][2] - cells[j][2]), (i - j + 1) // 2, (s["from"], s["to"], i))
            for c in cells:                                                       # never through a part
                for r in parts.values():
                    self.assertFalse(r["x1"] <= c[0] <= r["x2"] and r["z1"] <= c[1] <= r["z2"])
            self.assertGreaterEqual(len(s["points"]), 2)
        seen, todo = set(), [next(iter(parts))]
        while todo:
            n = todo.pop()
            if n not in seen:
                seen.add(n)
                todo += adj[n]
        self.assertEqual(seen, set(parts))

    def test_deterministic_and_fast(self):
        n = 256
        top = {(x, z): int(10 + 12 * math.sin(x / 20) * math.cos(z / 25)) for x in range(n) for z in range(n)}
        t0 = time.time()
        a = layout.plan(top, [0, 0, n - 1, n - 1], self.parts, 5)
        self.assertLess(time.time() - t0, 2.0)
        self.assertEqual(a, layout.plan(top, [0, 0, n - 1, n - 1], self.parts, 5))

    def test_errors_and_session_tool(self):
        with self.assertRaises(layout.LayoutError):
            layout.plan(self.top, [0, 0, 20, 20], [{"name": "big", "w": 60, "l": 60, "kind": "castle"}])
        with self.assertRaises(layout.LayoutError):
            layout.plan(self.top, [0, 0, 20, 20], [{"name": "a", "w": 5, "l": 5, "kind": "tower"}])
        s = session.start("Plan", terrain=hill_file(60))
        text, plan = session.plan_layout_text(s, [0, 0, 59, 59], [{"name": "c", "w": 12, "l": 12, "kind": "castle"},
                                                                     {"name": "h", "w": 7, "l": 7, "kind": "house"}])
        self.assertIn("Layout plan", text)
        self.assertEqual(len(plan["streets"]), 1)
        out = call("plan_layout", {"session": s.id, "area": [0, 0, 59, 59],
                                   "parts": [{"name": "c", "w": 12, "l": 12, "kind": "castle"}]}, 3)
        self.assertIn("castle", out["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
