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

        with mock.patch.object(engine, "find_claude", return_value="claude"), mock.patch.object(loop, "_spawn", spawn), \
                mock.patch.object(loop, "newest_build", lambda *a, **k: None):     # the id must come from the save result itself
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

    def test_missing_save_keeps_the_unfinished_build(self):
        with mock.patch.object(engine, "find_claude", return_value="claude"), \
                mock.patch.object(loop, "_spawn", lambda *a: FakeProc(SCRIPT[:3])), \
                mock.patch.object(loop, "newest_build", lambda *a, **k: None):
            meta = engine.generate("A well", size="tiny", engine="claude_loop", research=False, log=lambda s: None)
            self.assertTrue(meta.get("id"))

    def setUp(self):
        if os.path.isfile(store.SETTINGS):
            os.remove(store.SETTINGS)

    def tearDown(self):
        self.setUp()

    def test_default_mode_is_step_by_step(self):
        self.assertEqual(store.DEFAULT_SETTINGS["build_mode"], "step_by_step")
        self.assertEqual(store.load_settings()["build_mode"], "step_by_step")

    def test_old_loop_value_is_an_alias(self):
        store.save_settings({"build_mode": "loop"})
        self.assertEqual(store.load_settings()["build_mode"], "step_by_step")
        with open(store.SETTINGS, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["build_mode"], "step_by_step")
        with open(store.SETTINGS, "w", encoding="utf-8") as f:
            json.dump({"build_mode": "loop"}, f)
        self.assertEqual(store.load_settings()["build_mode"], "step_by_step")
        store.save_settings({"build_mode": "script"})
        self.assertEqual(store.load_settings()["build_mode"], "script")

    def _which(self, **kw):
        """Run generate() with both paths stubbed; return which one ran and the log."""
        lines = []
        with mock.patch.object(engine, "find_claude", return_value="claude"),                 mock.patch.object(engine, "_generate_loop", lambda *a: {"id": "loop"}),                 mock.patch.object(engine, "_Conversation", side_effect=RuntimeError("script")):
            try:
                r = engine.generate("A well", size="tiny", research=False, log=lines.append, **kw)
                return r["id"], lines
            except Exception as e:
                return str(e), lines

    def test_default_uses_step_by_step(self):
        self.assertEqual(self._which()[0], "loop")

    def test_script_setting_uses_script(self):
        store.save_settings({"build_mode": "script"})
        self.assertEqual(self._which()[0], "script")
        self.assertEqual(self._which(build_mode="step_by_step")[0], "loop")

    def test_api_engine_falls_back_to_script(self):
        who, lines = self._which(engine="api")
        self.assertEqual(who, "script")
        self.assertTrue(any("one-script" in l for l in lines))
        self.assertEqual(self._which(engine="openai")[0], "script")

    def test_edit_falls_back_to_script(self):
        with mock.patch.object(store, "get_code", return_value="x"), mock.patch.object(store, "edit_base", return_value=(None, None)):
            who, lines = self._which(parent_id="abcd1234")
        self.assertEqual(who, "script")
        self.assertTrue(any("edit" in l for l in lines))


if __name__ == "__main__":
    unittest.main()


class NoBuildMixUp(unittest.TestCase):
    def test_newest_build_never_returns_an_older_build(self):
        import time
        older = {"id": "old-1", "source": "claude_chat", "created": time.time()}
        with mock.patch.object(store, "list_builds", lambda: [older]):
            self.assertIsNone(loop.newest_build(time.time(), {"old-1"}))       # made just before this run: never ours
            self.assertEqual(loop.newest_build(time.time())["id"], "old-1")    # without the list the old rule would pick it
