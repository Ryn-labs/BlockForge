import base64
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

from tests import _env  # noqa: F401
from blockforge import mcp_server, session, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOOR = "fill(0,0,0,6,0,6,'stone_bricks')\n"


class SessionTools(unittest.TestCase):
    def test_flow(self):
        s = session.start("Test hut", "small")
        self.assertTrue(os.path.exists(os.path.join(session.DIR, s.id + ".json")))
        r = session.step(s, FLOOR, "floor")
        self.assertIn("49 added", r)
        r = session.step(s, "fill(0,1,0,6,3,6,'oak_planks', hollow=True)\n", "walls")
        self.assertEqual(len(session.load(s.id).history), 2)
        self.assertIn("added", r)
        session.undo(s, 1)
        s = session.load(s.id)                                  # survives a restart
        self.assertEqual(len(s.blocks), 49)
        self.assertEqual(len(s.history), 1)
        self.assertIn("floor", session.history_text(s))
        self.assertIn("Size", session.describe_text(s))

    def test_overwrite_and_bad_step(self):
        s = session.start("x")
        session.step(s, FLOOR)
        r = session.step(s, "fill(0,0,0,1,0,1,'dirt')\n")
        self.assertIn("4 existing blocks were overwritten", r)
        with self.assertRaises(session.SessionError):
            session.step(s, "this is not python (")
        self.assertEqual(len(s.history), 2)

    def test_view_png(self):
        s = session.start("v")
        session.step(s, FLOOR + "fill(1,1,1,5,4,5,'oak_planks', hollow=True)\n")
        pics = session.view(s)
        self.assertEqual([p[0] for p in pics], ["north", "east", "south", "west", "top"])
        for _, png in pics:
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            w, h = struct.unpack(">II", png[16:24])
            self.assertTrue(0 < w <= 512 and 0 < h <= 512)
        with self.assertRaises(session.SessionError):
            session.view(s, ["up"])

    def test_check_finds_buried_stair(self):
        s = session.start("c")
        session.step(s, FLOOR)
        r = session.step(s, "block(3,1,3,B('oak_stairs', facing='north', half='bottom'))\nblock(3,2,3,'stone_bricks')\n")
        self.assertIn("buried path", r)
        self.assertIn("(3, 1, 3)", session.check_text(s))

    def test_walk_finds_jump(self):
        s = session.start("w")
        session.step(s, "fill(0,0,0,5,0,2,'stone_bricks')\nfill(3,1,0,5,1,2,'stone_bricks')\n")
        out = session.walk(s, [[0, 1], [5, 1]])
        self.assertIn("Jump of 1 blocks going from (2, 0, 1) to (3, 1, 1)", out)
        ok = session.walk(s, [[0, 1], [2, 1]])
        self.assertIn("No problems", ok)

    def test_walk_headroom_and_no_floor(self):
        s = session.start("h")
        session.step(s, "fill(0,0,0,4,0,0,'stone_bricks')\nfill(2,2,0,2,2,0,'oak_planks')\nfill(1,3,0,3,3,0,'oak_planks')\n")
        out = session.walk(s, [[0, 0], [6, 0]])
        self.assertIn("head room", out)
        self.assertIn("No floor at x=5", out)

    def test_save_build(self):
        s = session.start("Saved hut")
        session.step(s, FLOOR + "fill(0,1,0,6,3,6,'oak_planks', hollow=True)\n")
        m, link = session.save(s)
        self.assertEqual(store.get_meta(m["id"])["source"], "claude_chat")
        self.assertIn("#1", link)

    def test_mcp_tool_calls(self):
        text = mcp_server.call("start_build", {"title": "via call"})
        sid = text.split()[2]
        mcp_server.call("build_step", {"session": sid, "code": FLOOR})
        res = mcp_server.call("view", {"session": sid, "sides": ["top"]})
        img = [c for c in res if c["type"] == "image"][0]
        self.assertEqual(base64.b64decode(img["data"])[:4], b"\x89PNG")
        with self.assertRaises(mcp_server.ToolError):
            mcp_server.call("check", {"session": "nope"})
        guide = mcp_server.call("get_build_guide", {})
        self.assertTrue(guide.startswith("# BlockForge"))
        self.assertLess(guide.index("HOW TO BUILD, PART BY PART"), guide.index("The build script"))


class McpStdio(unittest.TestCase):
    def test_stdio(self):
        tmp = tempfile.mkdtemp(prefix="bf_mcp_")
        env = dict(os.environ, BLOCKFORGE_DATA=tmp, BLOCKFORGE_PORT="8799", BLOCKFORGE_CLAUDE_HOME=tmp)
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "start_build", "arguments": {"title": "T"}}},
        ]
        p = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "blockforge", "mcp_server.py")], env=env, cwd=ROOT,
                           input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, timeout=60)
        replies = {r["id"]: r for r in map(json.loads, p.stdout.strip().splitlines())}
        names = {t["name"] for t in replies[2]["result"]["tools"]}
        for n in ("start_build", "build_step", "view", "check", "walk_test", "undo", "history", "describe", "save_build"):
            self.assertIn(n, names)
        out = replies[3]["result"]
        self.assertNotIn("isError", out)
        self.assertIn("started", out["content"][0]["text"])
        self.assertTrue(os.listdir(os.path.join(tmp, "sessions")))


if __name__ == "__main__":
    unittest.main()
