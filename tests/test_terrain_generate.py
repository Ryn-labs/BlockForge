import io
import json
import os
import re
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from blockforge import engine, loop, mcp_server, session, store, terrain
from tests.test_terrain import hill_file


class TerrainProc:
    """Stands in for claude.exe on a terrain build: the session already exists (its id is in the prompt)."""

    def __init__(self, script):
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None
        self.err_file = io.BytesIO()
        self.stdout = self._play(script)

    def _play(self, script):
        sid = re.search(r"(?:Build session |Session id: )(\w+)(?: is ALREADY started)?", self.stdin.getvalue().decode("utf-8")).group(1)
        n = 0
        for name, args in script:
            n += 1
            args = dict(args, session=sid) if "session" in args else args
            yield json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"t{n}", "name": "mcp__blockforge__" + name, "input": args}]}}).encode() + b"\n"
            out = mcp_server.handle({"method": "tools/call", "id": n, "params": {"name": name, "arguments": args}})
            yield json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"t{n}", "content": out["content"],
                 "is_error": bool(out.get("isError"))}]}}).encode() + b"\n"
        yield json.dumps({"type": "result", "is_error": False, "result": "done", "num_turns": n, "duration_ms": 1000,
                          "total_cost_usd": 0.05, "modelUsage": {"m": {"inputTokens": 100, "outputTokens": 50}}}).encode() + b"\n"

    def wait(self):
        return 0

    def kill(self):
        pass


class FakeConversation:
    reply = "Hill hut\n```python\nfill(5,10,5,9,14,9,'oak_planks', hollow=True)\n```"
    texts = []

    def __init__(self, engine_, model, settings, usage, text, *a, **k):
        FakeConversation.texts.append(text)

    def first(self):
        return self.reply

    def follow_up(self, message, code):
        return self.reply


class GenerateOnTerrain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = hill_file(30)

    def test_step_by_step_starts_on_the_terrain(self):
        top = terrain.ground_top(terrain.load(self.path))
        y = top[(4, 4)] + 1
        script = [("describe", {"session": "x"}), ("ground", {"session": "x", "x1": 0, "z1": 0, "x2": 6, "z2": 6}),
                  ("build_step", {"session": "x", "code": f"fill(3,{y},3,6,{y + 3},6,'oak_planks', hollow=True)\n", "note": "hut"}),
                  ("check", {"session": "x"}),
                  ("save_build", {"session": "x", "title": "Hill hut",               # a bare test hut: below the quality gate
                                  "keep_quality_user_answer": "a bare box is fine for this test"})]
        captured, lines = {}, []

        def spawn(cmd, work, env):
            captured["cmd"] = cmd
            return TerrainProc(script)

        with mock.patch.object(engine, "find_claude", return_value="claude"), mock.patch.object(loop, "_spawn", spawn):
            meta = engine.generate("A hut on the hill", size="large", engine="claude_loop", research=False, log=lines.append,
                                   terrain=self.path)
        self.assertGreater(meta["block_count"], 30 * 30)                     # the land is saved with the build
        b = store.get_blocks(meta["id"])
        self.assertGreater(len(b["blocks"]) // 4, 30 * 30 * 5 + 40)
        cmd = captured["cmd"]
        allowed = cmd[cmd.index("--allowedTools") + 1]
        self.assertIn("mcp__blockforge__ground", allowed)
        self.assertIn("mcp__blockforge__plan_layout", allowed)
        text = "\n".join(lines)
        self.assertIn("Reading the ground height", text)
        self.assertIn("Checks:", text)

    def test_script_mode_builds_on_the_terrain_as_a_new_build(self):
        FakeConversation.texts = []
        lines = []
        with mock.patch.object(engine, "_Conversation", FakeConversation):
            meta = engine.generate("A hut on the hill", size="large", engine="claude_code", build_mode="script", research=False,
                                   use_mods=False, log=lines.append, terrain=self.path)
        self.assertIsNone(meta.get("parent"))
        self.assertFalse(meta.get("base"))
        n_land = len(terrain.load(self.path))
        self.assertGreater(meta["block_count"], n_land)                      # land + the hut
        self.assertLess(meta["block_count"], n_land + 100)
        prompt = FakeConversation.texts[0]
        self.assertIn("building ON terrain", prompt)
        self.assertIn("Ground height", prompt)
        self.assertNotIn("Target size", prompt)
        self.assertIn("Building on the terrain", "\n".join(lines))

    def test_terrain_and_parent_do_not_mix(self):
        with self.assertRaises(engine.EngineError):
            engine.generate("x", terrain=self.path, parent_id="abcd1234", log=lambda s: None)
        with mock.patch.object(engine, "_Conversation", FakeConversation), self.assertRaises(engine.EngineError):
            engine.generate("x", build_mode="script", engine="claude_code", terrain="nothing-here", log=lambda s: None)


if __name__ == "__main__":
    unittest.main()
