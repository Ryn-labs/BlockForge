import json
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from tests.test_loop import FakeProc, SCRIPT
from blockforge import engine, loop


class EndingProc(FakeProc):
    """A transcript whose final result is replaced: how claude.exe ends a run on the turn cap or a real account limit."""

    def __init__(self, script, final):
        self.final = final
        super().__init__(script)

    def _play(self, script):
        for line in super()._play(script):
            if json.loads(line).get("type") == "result":
                line = json.dumps(dict({"type": "result", "num_turns": len(script), "duration_ms": 1000, "total_cost_usd": 0.05},
                                       **self.final)).encode() + b"\n"
            yield line


def run(final, script=SCRIPT[:3]):
    with mock.patch.object(engine, "find_claude", return_value="claude"), \
            mock.patch.object(loop, "_spawn", lambda *a: EndingProc(script, final)), \
            mock.patch.object(loop, "newest_build", lambda *a, **k: None):
        return engine.generate("A well", size="tiny", engine="claude_loop", research=False, log=lambda s: None)


class TurnCap(unittest.TestCase):
    def test_turn_cap_keeps_the_build(self):
        meta = run({"is_error": True, "subtype": "error_max_turns", "result": "", "usage": {"limit_hint": "x"}})
        self.assertTrue(meta.get("id"))
        self.assertGreater(meta["block_count"], 40)

    def test_real_usage_limit_is_named(self):
        with self.assertRaises(engine.EngineError) as e:
            run({"is_error": True, "result": "Claude AI usage limit reached|1764320000"})
        self.assertIn("usage limit", str(e.exception))

    def test_other_error_with_the_word_limit_is_not_a_usage_limit(self):
        with self.assertRaises(engine.EngineError) as e:
            run({"is_error": True, "result": "Output size limit exceeded for this tool"})
        self.assertNotIn("usage limit", str(e.exception))
        self.assertIn("Claude returned an error", str(e.exception))

    def test_turn_cap_is_configurable_and_higher(self):
        self.assertGreaterEqual(loop.MAX_TURNS, 200)


if __name__ == "__main__":
    unittest.main()
