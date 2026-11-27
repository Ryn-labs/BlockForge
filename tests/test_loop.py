import io
import json
import os
import re
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from blockforge import engine, loop, mcp_server, store


class FakeProc:
    """Stands in for claude.exe: plays a stream-json transcript, running every tool call on the real session tools."""

    def __init__(self, script):
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None
        self.err_file = io.BytesIO()
        self.stdout = self._play(script)
        self.sent = []

    def _play(self, script):
        n, sid = 0, None
        for name, args in script:
            n += 1
            if sid and "session" in args:
                args = dict(args, session=sid)
            yield json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"t{n}", "name": "mcp__blockforge__" + name, "input": args}]}}).encode() + b"\n"
            out = mcp_server.handle({"method": "tools/call", "id": n, "params": {"name": name, "arguments": args}})
            if name == "start_build":
                sid = re.search(r"session (\w+)", out["content"][0]["text"]).group(1)
            yield json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"t{n}", "content": out["content"],
                 "is_error": bool(out.get("isError"))}]}}).encode() + b"\n"
        yield json.dumps({"type": "result", "is_error": False, "result": "done", "num_turns": n, "duration_ms": 1000,
                          "total_cost_usd": 0.05,
                          "modelUsage": {"m": {"inputTokens": 100, "outputTokens": 50}}}).encode() + b"\n"

    def wait(self):
        return 0

    def kill(self):
        pass


SCRIPT = [
    ("start_build", {"title": "Test well", "size_hint": "tiny"}),
    ("build_step", {"session": "x", "code": "fill(0,0,0,4,0,4,'stone_bricks')\n", "note": "base"}),
    ("build_step", {"session": "x", "code": "fill(0,1,0,4,3,4,'oak_planks', hollow=True)\n", "note": "walls"}),
    ("view", {"session": "x", "sides": ["north"]}),
    ("check", {"session": "x"}),
    ("save_build", {"session": "x", "title": "Test well"}),
]


class LoopEngine(unittest.TestCase):
    def test_generate_with_fake_claude(self):
        lines = []
        captured = {}

        def spawn(cmd, work, env):
            captured["cmd"] = cmd
            with open(cmd[cmd.index("--mcp-config") + 1], encoding="utf-8") as f:
                captured["cfg"] = json.load(f)
            return FakeProc(SCRIPT)

        with mock.patch.object(engine, "find_claude", return_value="claude"), mock.patch.object(loop, "_spawn", spawn):
            meta = engine.generate("A small stone well", size="tiny", engine="claude_loop", research=False, log=lines.append)
        self.assertEqual(store.get_meta(meta["id"])["title"], "Test well")
        self.assertGreater(meta["block_count"], 40)
        self.assertIn("total", meta["checks"])
        self.assertIn("by_check", meta["checks"])
        self.assertEqual(meta["usage"]["engine"], "claude_loop")
        self.assertAlmostEqual(meta["usage"]["cost_usd"], 0.05)
        text = "\n".join(lines)
        self.assertIn("Building part: walls", text)
        self.assertIn("Looking at the build", text)
        self.assertIn("Checks:", text)
        cmd = captured["cmd"]
        self.assertIn("--strict-mcp-config", cmd)
        self.assertIn("mcp__blockforge__build_step", cmd[cmd.index("--allowedTools") + 1])
        self.assertNotIn("Bash", cmd[cmd.index("--allowedTools") + 1])
        self.assertIn("blockforge", captured["cfg"]["mcpServers"])
        self.assertEqual(captured["cfg"]["mcpServers"]["blockforge"]["env"]["BLOCKFORGE_DATA"], store.DATA)

    def test_missing_save_is_an_error(self):
        with mock.patch.object(engine, "find_claude", return_value="claude"), \
                mock.patch.object(loop, "_spawn", lambda *a: FakeProc(SCRIPT[:3])), \
                mock.patch.object(loop, "newest_build", lambda since: None):
            with self.assertRaises(engine.EngineError):
                engine.generate("A well", size="tiny", engine="claude_loop", research=False, log=lambda s: None)

    def test_default_mode_is_script(self):
        self.assertEqual(store.DEFAULT_SETTINGS["build_mode"], "script")


if __name__ == "__main__":
    unittest.main()
