"""The spiral stair patterns pass checks.py and the benchmark scorer with zero path problems."""
import json, os, sys, tempfile, unittest

from tests import _env  # noqa: F401
from blockforge import checks, patterns, sandbox
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench"))
import score as S

PATH_KINDS = ("buried_path", "jump_step", "door_blocked", "floating", "headroom", "wrong_facing", "corner_turn")
ZERO = ("buried_path", "jump_steps", "corner_turns", "wrong_facing", "blocked_doors", "floating")

CASES = {
    "round_r3": lambda: patterns.round_tower_with_stair(5, 1, 5, 3, 12),
    "round_r5": lambda: patterns.round_tower_with_stair(8, 1, 8, 5, 26),
    "round_r5_ccw": lambda: patterns.spiral_stair(8, 1, 8, 5, 20, direction="ccw"),
    "round_r8_cobble": lambda: patterns.round_tower_with_stair(10, 1, 10, 8, 30, "cobblestone", "cobblestone_stairs"),
    "square_5": lambda: patterns.square_spiral_stair(2, 2, 5, 1, 14),
    "square_9": lambda: patterns.square_spiral_stair(2, 2, 9, 1, 24),
}


def build_dir(blocks):
    d = tempfile.mkdtemp(prefix="bf-spiral-test-")
    pal = sorted(set(blocks.values())); idx = {p: i for i, p in enumerate(pal)}
    flat = []
    for (x, y, z), s in blocks.items():
        flat += [x, y, z, idx[s]]
    size = [max(p[i] for p in blocks) + 1 for i in range(3)]
    json.dump({"size": size, "palette": pal, "blocks": flat}, open(os.path.join(d, "blocks.json"), "w"))
    json.dump({"title": "t", "fixes": []}, open(os.path.join(d, "meta.json"), "w"))
    return d


class Spiral(unittest.TestCase):
    def test_clean(self):
        for name, make in CASES.items():
            with self.subTest(name):
                blocks, meta = sandbox.run_safe(make())
                self.assertEqual(meta.get("warnings"), [])
                self.assertEqual(meta.get("fixes"), [])
                found = [f for f in checks.run(blocks) if f["check"] in PATH_KINDS]
                self.assertEqual(found, [], [f["text"] for f in found])
                sc = S.score(build_dir(blocks))
                for k in ZERO:
                    self.assertEqual(sc[k], 0, (k, sc))

    def test_climbs_to_the_top_floor_and_has_a_door(self):
        blocks, _ = sandbox.run_safe(patterns.round_tower_with_stair(8, 1, 8, 5, 20))
        self.assertTrue(any("_door" in s for s in blocks.values()))
        self.assertTrue(any("glass_pane" in s for s in blocks.values()))
        stairs_y = sorted(p[1] for p, s in blocks.items() if "stone_brick_stairs" in s)
        self.assertEqual((stairs_y[0], stairs_y[-1]), (1, 20))
        self.assertTrue(any(p[1] == 20 and s.endswith(":stone_bricks") or s == "stone_bricks" for p, s in blocks.items()))

    def test_a_turn_climbs_at_least_four(self):
        for k in (1, 2, 3):
            ring = patterns._ring_cw(0, 0, 2 * k, 2 * k)
            items = patterns._spiral_path(ring, 1, 60)
            first = [it for it in items if (it[0], it[1]) == (ring[1][0], ring[1][1])]
            self.assertGreaterEqual(first[1][2] - first[0][2], 4)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            patterns.round_tower_with_stair(5, 1, 5, 2, 12)
        with self.assertRaises(ValueError):
            patterns.square_spiral_stair(0, 0, 4, 1, 12)
        with self.assertRaises(ValueError):
            patterns.spiral_stair(5, 1, 5, 4, 12, direction="up")

    def test_listed_by_the_pattern_tool(self):
        from blockforge import mcp_server
        text = mcp_server.call("pattern", {"name": "nope"})
        for n in ("spiral_stair(", "square_spiral_stair(", "round_tower_with_stair("):
            self.assertIn(n, text)


if __name__ == "__main__":
    unittest.main()
