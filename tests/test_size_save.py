"""save_build refuses a build that is more than 10% outside the asked size, unless accept_problems explains it."""
import unittest

from tests import _env  # noqa: F401
from blockforge import mcp_server, prompts

FLOOR = "fill(0,0,0,6,0,6,'stone_bricks')\n"            # 7 x 1 x 7


def start(hint):
    text = mcp_server.call("start_build", {"title": "size test", "size_hint": hint})
    sid = text.split()[2]
    mcp_server.call("build_step", {"session": sid, "code": FLOOR + "fill(0,1,0,6,3,6,'oak_planks', hollow=True)\n"})
    return sid


class SizeParse(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(prompts.parse_size_hint("a medium castle"), "medium")
        self.assertEqual(prompts.parse_size_hint("24 x 16 x 30 cottage"), {"w": 24, "h": 16, "l": 30, "exact": True})
        self.assertEqual(prompts.parse_size_hint("40x20 farm"), {"w": 40, "l": 20, "exact": True})
        self.assertIsNone(prompts.parse_size_hint("cosy hut"))
        self.assertIsNone(prompts.parse_size_hint(""))

    def test_problem(self):
        self.assertIsNone(prompts.size_problem("small", (20, 10, 20)))
        self.assertIsNone(prompts.size_problem("small", (15, 10, 15)))           # inside 10% of the range
        self.assertIn("'small'", prompts.size_problem("small", (7, 4, 7)))
        self.assertIn("7 wide", prompts.size_problem("small", (7, 4, 7)))
        self.assertIsNone(prompts.size_problem("no size here", (7, 4, 7)))
        self.assertIn("24 wide", prompts.size_problem("24 x 16 x 30", (7, 4, 7)))
        self.assertIsNone(prompts.size_problem("24 x 16 x 30", (24, 16, 30)))


class SaveRefusal(unittest.TestCase):
    def test_refuses_a_too_small_build(self):
        sid = start("large tower")
        with self.assertRaises(mcp_server.ToolError) as cm:
            mcp_server.call("save_build", {"session": sid})
        msg = str(cm.exception)
        self.assertIn("size is off", msg)
        self.assertIn("7 wide", msg)                    # current size
        self.assertIn("64-96", msg)                     # target

    def test_accept_problems_lets_it_through(self):
        sid = start("large tower")
        out = mcp_server.call("save_build", {"session": sid, "accept_problems": "a tiny model of the tower on purpose"})
        self.assertIn("size test", out)

    def test_right_size_saves(self):
        sid = start("7 x 4 x 7 shed")
        out = mcp_server.call("save_build", {"session": sid})
        self.assertIn("size test", out)

    def test_no_hint_saves(self):
        sid = start("")
        mcp_server.call("save_build", {"session": sid})


if __name__ == "__main__":
    unittest.main()
