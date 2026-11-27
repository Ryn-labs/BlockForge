"""Bench prompt 11 (a town on a hill): the fixed terrain, the terrain-aware scorer, and the runner with a mocked engine."""
import json
import os
import runpy
import shutil
import sys
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_bench_score import build
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import make_terrain  # noqa: E402
import score as S  # noqa: E402
from blockforge import exporters, store, terrain  # noqa: E402


def flat_land(n=14, h=3):
    return {(x, y, z): "minecraft:stone" for x in range(n) for z in range(n) for y in range(h)}


def named(blocks):
    return {p: s.replace("minecraft:", "") for p, s in blocks.items()}


class FixedTerrain(unittest.TestCase):
    def test_hill_is_committed_small_and_deterministic(self):
        path = os.path.join(ROOT, "bench", "terrain", "hill.schem")
        self.assertTrue(os.path.isfile(path))
        self.assertLess(os.path.getsize(path), 1_000_000)
        land = terrain.load(path)
        lo_x, lo_z, hi_x, hi_z, lo_y, hi_y = terrain.bounds(land)
        self.assertEqual((hi_x - lo_x + 1, hi_z - lo_z + 1), (160, 160))
        self.assertLessEqual(hi_y - lo_y + 1, 70)
        self.assertEqual(land, make_terrain.build())               # same seed, same land
        top = terrain.ground_top(land, land)
        hill = max(top, key=top.get)
        self.assertGreater(top[hill], 45)                           # one clear highest hill for the castle
        names = {s for s in land.values()}
        self.assertTrue({"minecraft:grass_block", "minecraft:dirt", "minecraft:stone", "minecraft:oak_log"} <= names)

    def test_prompt_11_is_in_the_list(self):
        p = {x["id"]: x for x in json.load(open(os.path.join(ROOT, "bench", "prompts.json")))}[11]
        self.assertEqual((p["key"], p["size"], p["terrain"]), ("hill_town", "large", "terrain/hill.schem"))
        self.assertIn("castle on the highest hill", p["prompt"])


class TerrainScore(unittest.TestCase):
    def test_floating_over_ground_and_buried_path(self):
        land = flat_land()
        b = dict(land)
        for x in range(4, 7):
            for z in range(4, 7):
                b[(x, 6, z)] = "minecraft:stone_bricks"                # a slab of bricks hanging 3 blocks over the ground
        res = S.score(build(b), terrain=named(land))
        self.assertEqual(res["terrain_floating"], 9)
        self.assertEqual(res["floating"], 0)
        self.assertNotIn("terrain_floating", S.score(build(b)))
        # a stair that has hill (terrain) on top of it
        b = dict(land)
        for z in range(1, 4):
            b[(5, 3, z)] = "minecraft:stone_brick_stairs[facing=east,half=bottom,shape=straight]"
        b[(5, 4, 2)] = "minecraft:stone"
        b[(5, 5, 2)] = "minecraft:stone"
        land2 = dict(land)
        land2[(5, 4, 2)] = "minecraft:stone"
        land2[(5, 5, 2)] = "minecraft:stone"
        res = S.score(build(b), terrain=named(land2))
        self.assertEqual((res["terrain_buried"], res["buried_path"]), (1, 0))
        res = S.score(build(b), terrain=named(land))               # the same block built by the AI is an ordinary buried path
        self.assertEqual((res["terrain_buried"], res["buried_path"]), (0, 1))

    def test_a_house_on_the_ground_is_fine(self):
        land = flat_land()
        b = dict(land)
        for x in range(4, 8):
            for z in range(4, 8):
                for y in range(3, 7):
                    if x in (4, 7) or z in (4, 7) or y == 6:
                        b[(x, y, z)] = "minecraft:oak_planks"
        res = S.score(build(b), terrain=named(land))
        self.assertEqual((res["terrain_floating"], res["floating"], res["terrain_buried"], res["buried_path"]), (0, 0, 0, 0))


class RunBenchPrompt11(unittest.TestCase):
    def test_runner_passes_the_terrain_and_scores_it(self):
        label = "unit-test-terrain"
        out = os.path.join(ROOT, "bench", "out", label)
        shutil.rmtree(out, ignore_errors=True)
        seen = {}

        def fake_generate(prompt, size="medium", terrain=None, log=print, **kw):
            seen.update(prompt=prompt, terrain=terrain, size=size, kw=kw)
            land = exporters.import_file(open(terrain, "rb").read())
            top = {}
            for (x, y, z) in land:
                top[(x, z)] = max(top.get((x, z), -1), y)
            b = dict(land)
            ox, oz = 100, 60
            y0 = top[(ox, oz)] + 1
            for x in range(ox, ox + 5):
                for z in range(oz, oz + 5):
                    for y in range(y0, y0 + 4):
                        if x in (ox, ox + 4) or z in (oz, oz + 4) or y == y0 + 3:
                            b[(x, y, z)] = "minecraft:stone_bricks"
            log("fake build")
            return store.save_build(b, "Hill town", prompt=prompt, source="claude_chat")

        argv = sys.argv
        sys.argv = ["run_bench.py", "--only", "11"]
        os.environ["BENCH_LABEL"] = label
        import render
        try:
            with mock.patch("blockforge.engine.generate", fake_generate), mock.patch.object(render, "sheet", lambda *a, **k: None):
                runpy.run_path(os.path.join(ROOT, "bench", "run_bench.py"), run_name="__main__")
            self.assertTrue(seen["terrain"].endswith(os.path.join("terrain", "hill.schem")))
            self.assertTrue(os.path.isabs(seen["terrain"]))
            self.assertIn("castle on the highest hill", seen["prompt"])
            self.assertIsNone(seen["kw"].get("parent_id"))
            rows = [json.loads(line) for line in open(os.path.join(out, "results.jsonl"), encoding="utf-8")]
            self.assertEqual([r["id"] for r in rows], [11])
            r = rows[0]
            self.assertNotIn("error", r)
            self.assertEqual((r["terrain_floating"], r["terrain_buried"], r["size_off"]), (0, 0, 0))
            self.assertIn("terrain_floating", open(os.path.join(out, "table.md"), encoding="utf-8").read())
        finally:
            sys.argv = argv
            os.environ.pop("BENCH_LABEL", None)
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
