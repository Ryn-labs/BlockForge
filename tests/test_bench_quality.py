"""The bench's quality column (bench/score.py -> blockforge.quality) and the three house prompts, tested on stored builds
(no AI calls, the real bench is never run here)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import _env  # noqa: F401
from tests.test_bench_score import S, build
from blockforge import examples, patterns, sandbox

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BenchQuality(unittest.TestCase):
    def test_quality_column_for_a_building(self):
        blocks, _ = sandbox.run_safe(examples.code("good_cottage"))
        out = S.score(build(blocks))
        self.assertGreaterEqual(out["quality"], 70)
        self.assertEqual(out["floating"], 0)

    def test_quality_column_uses_the_prompt_for_bench_builds(self):
        for name, prompt, lo, hi in (("bench_wooden_manor_blocks.json", "A wooden manor with log frames, a layered roof, "
                                      "a balcony, window boxes and a terrace garden.", 0, 59),
                                     ("bench_dark_manor_1130_blocks.json", "A wooden manor with log frames, a layered "
                                      "roof, a balcony, window boxes and a terrace garden.", 0, 59),
                                     ("bench_small_cottage_blocks.json", "A small cottage.", 30, 59)):
            with self.subTest(name):
                d = tempfile.mkdtemp(prefix="bf-quality-bench-")
                try:
                    shutil.copy(os.path.join(ROOT, "tests", "data", name), os.path.join(d, "blocks.json"))
                    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
                        json.dump({"title": "t", "prompt": prompt, "fixes": []}, f)
                    q = S.score(d)["quality"]
                finally:
                    shutil.rmtree(d, ignore_errors=True)
                self.assertGreaterEqual(q, lo)
                self.assertLessEqual(q, hi)

    def test_no_quality_for_a_bridge(self):
        blocks, _ = sandbox.run_safe(patterns.stone_arch_bridge(2, 6, 2, 11, 3))
        self.assertIsNone(S.score(build(blocks))["quality"])

    def test_terrain_builds_score_what_was_built(self):
        land = {(x, 0, z): "grass_block" for x in range(30) for z in range(30)}
        self.assertIsNone(S.quality_total(dict(land), land))

    def test_house_prompts(self):
        with open(os.path.join(ROOT, "bench", "prompts.json"), encoding="utf-8") as f:
            prompts = {p["id"]: p for p in json.load(f)}
        self.assertEqual(prompts[12], {"id": 12, "key": "wooden_manor", "size": "large", "prompt": "A wooden manor with log "
                                       "frames, a layered roof, a balcony, window boxes and a terrace garden."})
        self.assertEqual(prompts[13], {"id": 13, "key": "farmhouse_fields", "size": "medium",
                                       "prompt": "A farmhouse with fields, a fenced yard and a small barn."})
        self.assertEqual(prompts[14], {"id": 14, "key": "small_cottage", "size": "small", "prompt": "A small cottage."})
        self.assertEqual([prompts[i]["key"] for i in (15, 16, 17)],                # natural terrain prompts
                         ["snowy_mountain", "mountain_valley_river", "hill_town_mountain"])
        self.assertEqual(len(prompts), 17)

    def test_table_shows_the_average_quality(self):
        label = "unit-test-quality"
        out = os.path.join(ROOT, "bench", "out", label)
        os.makedirs(out, exist_ok=True)
        try:
            rows = [{"id": 12, "key": "wooden_manor", "quality": 90, "floating": 0},
                    {"id": 14, "key": "small_cottage", "quality": 70, "floating": 1},
                    {"id": 5, "key": "arch_bridge", "quality": None}]
            with open(os.path.join(out, "results.jsonl"), "w", encoding="utf-8") as f:
                f.write("".join(json.dumps(r) + "\n" for r in rows))
            p = subprocess.run([sys.executable, os.path.join(ROOT, "bench", "table.py"), label], capture_output=True,
                               text=True, timeout=60)
            self.assertIn("TABLE_OK", p.stdout, p.stderr)
            with open(os.path.join(out, "table.md"), encoding="utf-8") as f:
                table = f.read()
            def cells(prefix):
                return [c.strip() for c in next(ln for ln in table.splitlines() if ln.startswith(prefix)).strip("|").split("|")]
            head, total = cells("| id"), cells("| total")
            self.assertEqual(total[head.index("quality")], "80")
            self.assertEqual(int(p.stdout.split("mistakes ")[1].split()[0]), 1)     # quality never counts as a mistake
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
