"""save_build refuses a building or town below quality.QUALITY_MIN; accept_problems does not waive it, only the user's answer
(keep_quality_user_answer) can, and never in unattended mode. review shows the pictures, the score and the rubric."""
import base64
import os
import unittest

from tests import _env  # noqa: F401
from blockforge import examples, loop, mcp_server, patterns, quality, store

BOX = ("fill(0,0,0,8,0,8,'cobblestone')\nwalls(0,1,0,8,4,8,'cobblestone')\nfill(0,5,0,8,5,8,'cobblestone')\n"
       "block(4,1,8,B('oak_door',facing='south',half='lower'))\nblock(4,2,8,B('oak_door',facing='south',half='upper'))\n")


def start(code, title="quality test"):
    text = mcp_server.call("start_build", {"title": title})
    sid = text.split()[2]
    mcp_server.call("build_step", {"session": sid, "code": code})
    return sid


class Gate(unittest.TestCase):
    def test_refuses_a_plain_box_with_the_three_weakest_parts(self):
        sid = start(BOX)
        with self.assertRaises(mcp_server.ToolError) as cm:
            mcp_server.call("save_build", {"session": sid})
        msg = str(cm.exception)
        self.assertIn("too plain", msg)
        self.assertIn(f"minimum of {quality.QUALITY_MIN}", msg)
        self.assertEqual(len([ln for ln in msg.splitlines() if ln.startswith("- ")]), 3)
        self.assertRegex(msg, r"\(-?\d+, -?\d+, -?\d+\)|x -?\d+\.\.-?\d+")     # concrete places to fix
        self.assertIn("keep_quality_user_answer", msg)

    def test_accept_problems_does_not_waive_quality(self):
        sid = start(BOX)
        with self.assertRaises(mcp_server.ToolError) as cm:
            mcp_server.call("save_build", {"session": sid, "accept_problems": "it is meant to be a simple box"})
        self.assertIn("accept_problems does not cover the quality", str(cm.exception))

    def test_users_answer_keeps_it(self):
        sid = start(BOX, "plain box")
        out = mcp_server.call("save_build", {"session": sid, "keep_quality_user_answer": "yes, keep the plain box"})
        self.assertIn("plain box", out)
        bid = out.split("(id ")[1].split(")")[0]
        q = store.get_meta(bid)["quality"]
        self.assertLess(q["total"], quality.QUALITY_MIN)
        self.assertTrue(q["kept_by_user"])

    def test_unattended_never_waives(self):
        sid = start(BOX)
        os.environ["BLOCKFORGE_UNATTENDED"] = "1"
        try:
            with self.assertRaises(mcp_server.ToolError) as cm:
                mcp_server.call("save_build", {"session": sid, "keep_quality_user_answer": "keep it"})
            self.assertNotIn("ask them", str(cm.exception))
        finally:
            os.environ.pop("BLOCKFORGE_UNATTENDED", None)

    def test_good_cottage_saves_with_its_score(self):
        sid = start(examples.code("good_cottage"), "pattern cottage")
        out = mcp_server.call("save_build", {"session": sid})
        self.assertIn("Quality:", out)
        bid = out.split("(id ")[1].split(")")[0]
        q = store.get_meta(bid)["quality"]
        self.assertGreaterEqual(q["total"], 70)
        self.assertFalse(q["kept_by_user"])

    def test_non_buildings_are_not_gated(self):
        sid = start(patterns.stone_arch_bridge(2, 6, 2, 11, 3), "bridge")
        out = mcp_server.call("save_build", {"session": sid})
        self.assertNotIn("Quality:", out)

    def test_towns_are_gated_too(self):
        from tests.test_quality import ROW
        sid = start(ROW, "row")
        with self.assertRaises(mcp_server.ToolError) as cm:
            mcp_server.call("save_build", {"session": sid})
        self.assertIn("the town looks too plain", str(cm.exception))


class Review(unittest.TestCase):
    def test_review_shows_pictures_score_and_rubric(self):
        sid = start(BOX)
        res = mcp_server.call("review", {"session": sid})
        imgs = [c for c in res if c["type"] == "image"]
        self.assertEqual(len(imgs), 5)
        self.assertEqual(base64.b64decode(imgs[0]["data"])[:4], b"\x89PNG")
        text = "\n".join(c["text"] for c in res if c["type"] == "text")
        for word in ("Facade depth", "Roof", "Massing", "Palette", "Detail", "Surroundings", "1-5", "below 4"):
            self.assertIn(word, text)
        self.assertIn("Fix first", text)

    def test_review_is_a_tool_everywhere(self):
        self.assertIn("review", {t["name"] for t in mcp_server.TOOLS})
        self.assertIn("review", mcp_server.SESSION_TOOLS)
        self.assertIn("review", loop.TOOLS)
        self.assertIn("review()", mcp_server._skill_text())


class HouseDefault(unittest.TestCase):
    def test_loop_prompt_starts_houses_and_towns_from_patterns(self):
        text = loop.system_prompt("A small cottage")
        self.assertIn("Houses and towns: start from the proven parts (default)", text)
        for part in ("framed_house", "framed_wall", "gable_roof_trim", "window_with_box", "porch", "balcony", "chimney",
                     "fence_garden", "plan_layout", "landmark", "3-6 materials"):
            self.assertIn(part, text)
        self.assertIn("never a bare box", loop.user_text("A small cottage"))
        self.assertIn("review", loop.user_text("A small cottage"))


if __name__ == "__main__":
    unittest.main()
