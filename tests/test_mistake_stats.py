import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests import _env  # noqa: F401
from blockforge import lessons, loop, mistake_stats as MS, engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Stats(unittest.TestCase):
    def setUp(self):
        self.old = MS.PATH
        MS.PATH = os.path.join(tempfile.mkdtemp(prefix="bf_ms_"), "mistake_stats.json")

    def tearDown(self):
        MS.PATH = self.old

    def test_empty(self):
        self.assertEqual(MS.top(), [])
        self.assertEqual(MS.lesson_lines(), [])
        self.assertEqual(lessons.for_ai()[0][:2], "- ")

    def test_record_top_lines(self):
        MS.record({"checks": {"by_check": {"buried_path": 6, "jump_step": 2, "headroom": 2, "floating": 0}}}, "app")
        MS.record({"floating": 1, "size_off": 5, "script_errors": 9}, "bench", key="cottage",
                  examples={"floating": ["floating part at (1, 2, 3)"]})
        t = MS.top()
        self.assertEqual([x[0] for x in t], ["buried_path", "size_off", "jump_steps", "floating"])
        self.assertEqual(t[0][1], 8)
        self.assertAlmostEqual(sum(x[2] for x in t), 1.0)
        self.assertEqual(t[3][3], ["floating part at (1, 2, 3)"])
        line = MS.lesson_lines(1)[0]
        self.assertIn("2 free blocks", line)
        self.assertIn("%", line)

    def test_window_and_examples(self):
        MS.record({"floating": 1}, "app")
        for i in range(MS.WINDOW):
            MS.record({"removed": 1}, "app", examples={"removed": [f"e{i}"]})
        t = dict((x[0], x) for x in MS.top(9))
        self.assertNotIn("floating", t)               # the oldest build fell out of the window
        self.assertEqual(t["removed"][1], MS.WINDOW)
        self.assertEqual(t["removed"][3], [f"e{MS.WINDOW - 3 + i}" for i in range(3)])

    def test_findings_and_dedup(self):
        found = [{"check": "door_blocked", "at": [1, 2, 3], "text": "door at 1 2 3 is blocked", "count": 2}]
        MS.record_findings(found, "app", build_id="b1")
        self.assertEqual(MS.record_findings(found, "app", build_id="b1"), {})
        self.assertEqual(MS.top()[0][:2], ("blocked_doors", 2))

    def test_feed_results(self):
        d = tempfile.mkdtemp(prefix="bf_feed_")
        rows = [{"id": 1, "key": "cottage", "version": "x", "build": "a", "buried_path": 4, "overwritten": 2, "fix_rounds": 5},
                {"id": 2, "key": "bridge", "version": "x", "build": "b", "buried_path": 1, "error": "boom"}]
        with open(os.path.join(d, "results-w0.jsonl"), "w") as f:
            f.write("\n".join(json.dumps(r) for r in rows) + "\n")
        for r in rows:
            MS.record_bench_row(r)
        self.assertEqual([(x[0], x[1]) for x in MS.top()], [("buried_path", 4), ("overwritten", 2)])
        # the script, on a fake bench/out label, writes to --stats
        label = "zz-test-feed"
        out = os.path.join(ROOT, "bench", "out", label)
        os.makedirs(out)
        try:
            shutil.move(os.path.join(d, "results-w0.jsonl"), os.path.join(out, "results-w0.jsonl"))
            stats = os.path.join(d, "s.json")
            r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "bench", "feed_lessons.py"), label, "--stats", stats],
                               capture_output=True, text=True, env=dict(os.environ))
            self.assertIn("FEED_OK", r.stdout, r.stderr)
            self.assertEqual(json.load(open(stats))["builds"][0]["source"], "bench")
        finally:
            for fn in os.listdir(out):
                os.remove(os.path.join(out, fn))
            os.rmdir(out)

    def test_prompts_have_block(self):
        MS.record({"buried_path": 3, "floating": 1}, "app")
        text = "\n".join(lessons.for_ai())
        self.assertIn("Your most common mistakes lately", text)
        self.assertLess(len(text.encode()), 3500)
        self.assertEqual(text.count("\n- ") + 1 >= 8, True)
        self.assertIn("Your most common mistakes lately", loop.system_prompt("a cottage"))
        self.assertIn("Your most common mistakes lately", engine._with_lessons("", "claude_code"))
        self.assertNotIn("Your most common mistakes lately", engine._with_lessons("learned", "claude_loop"))


if __name__ == "__main__":
    unittest.main()
