"""The builder improves its own work: chat rounds, step-by-step extra turns, and the MCP "NOT DONE YET" results."""
import json
import re
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from blockforge import chat, engine, examples, loop, mcp_server, quality, selfimprove, session, store
from tests.test_chat import Ai, FakeProc
from tests import test_loop

COTTAGE = examples.code("good_cottage")
BOX = ("fill(0,0,0,8,0,8,'cobblestone')\nwalls(0,1,0,8,4,8,'cobblestone')\nfill(0,5,0,8,5,8,'cobblestone')\n"
       "block(4,1,8,B('oak_door',facing='south',half='lower'))\nblock(4,2,8,B('oak_door',facing='south',half='upper'))\n"
       "block(4,4,4,B('lantern',hanging=True))\n")                  # lit inside: plain, but no check problem
FLOAT = "block(30,20,30,'stone')\n"                      # nothing under it: one floating-part problem
CLEAR_ALL = "clear(-10,-10,-10,80,80,80)\n"


def problems(sid):
    s = session.load(sid)
    return selfimprove.assess(s.blocks, s.ground(), s.terrain_blocks, s.size_hint)


class ChatSelfImprove(unittest.TestCase):
    def test_a_bad_turn_improves_itself_and_says_what_changed(self):
        ai = Ai(self, [
            ([("build_step", {"code": BOX + FLOAT, "note": "plain house"})], "Built the house."),
            ([("build_step", {"code": CLEAR_ALL + COTTAGE, "note": "better"}), ("check", {})], "Fixed it."),
        ])
        c = chat.create("A small stone house")
        cid = ai.cid = c["id"]
        logs = []
        res = chat.run_turn(cid, "A small stone house", add_user=False, log=logs.append)
        self.assertEqual(res["rounds"], 1)
        c = chat.load(cid)
        self.assertEqual(ai.replies, [])
        # status line in the panel, versions recorded (start, first turn, round 1)
        self.assertIn("Improving: floating parts, round 1 of 3", [m["text"] for m in c["messages"] if m["role"] == "system"])
        self.assertTrue(any(l.startswith("Improving: floating parts, round 1 of 3") for l in logs))
        self.assertEqual([v["id"] for v in c["versions"]], ["v1", "v2", "v3"])
        self.assertTrue(c["versions"][-1]["note"].startswith("Improving:"))
        # the message of the improvement turn carries the findings and says "change nothing else"
        self.assertIn("Automatic improvement round 1 of 3", ai.users[1])
        self.assertIn("floating parts (1)", ai.users[1])
        self.assertIn("Quality", ai.users[1])
        self.assertIn("change nothing else", ai.users[1])
        # the hand-back message: before/after numbers, and the build is clean now
        last = c["messages"][-1]
        self.assertEqual(last["role"], "ai")
        self.assertRegex(last["text"], r"Fixed 1 check problem \(floating parts 1\); quality \d+ -> \d+")
        self.assertEqual(last["improved"]["after"]["problems"], 0)
        self.assertGreaterEqual(last["improved"]["after"]["quality"], quality.QUALITY_MIN)
        self.assertNotIn("keep_improving", last)
        self.assertTrue(problems(c["session"])["ok"])
        self.assertEqual(c["versions"][-1]["check"]["total"], 0)

    def test_rounds_are_capped_and_keep_improving_is_offered(self):
        stay = ([], "I looked, nothing to change.")
        ai = Ai(self, [([("build_step", {"code": BOX + FLOAT, "note": "plain house"})], "Built."), stay, stay, stay,
                       ([("build_step", {"code": CLEAR_ALL + COTTAGE, "note": "better"})], "Fixed.")])
        c = chat.create("A small stone house")
        cid = ai.cid = c["id"]
        res = chat.run_turn(cid, "A small stone house", add_user=False, log=lambda m: None)
        self.assertEqual(res["rounds"], selfimprove.CHAT_ROUNDS)
        c = chat.load(cid)
        self.assertEqual(len(ai.replies), 1)                                  # a 4th round never started
        lines = [m["text"] for m in c["messages"] if m.get("status")]
        self.assertEqual(lines, [f"Improving: floating parts, round {k} of 3" for k in (1, 2, 3)])
        last = c["messages"][-1]
        self.assertTrue(last["keep_improving"])
        self.assertIn("still open", last["text"])
        self.assertIn("floating parts 1", last["text"])
        self.assertIn("Keep improving", last["text"])
        # the button: more rounds, quality counts, ends clean
        self.assertEqual(chat.improve(cid, log=lambda m: None)["rounds"], 1)
        c = chat.load(cid)
        self.assertNotIn("keep_improving", c["messages"][-1])
        self.assertTrue(problems(c["session"])["ok"])
        self.assertNotIn(cid, chat._BUSY)

    def test_a_clean_turn_gets_no_rounds(self):
        ai = Ai(self, [([("build_step", {"code": COTTAGE, "note": "cottage"})], "Built.")])
        c = chat.create("A cottage")
        cid = ai.cid = c["id"]
        self.assertEqual(chat.run_turn(cid, "A cottage", add_user=False, log=lambda m: None)["rounds"], 0)
        self.assertEqual(len(chat.load(cid)["versions"]), 2)
        self.assertNotIn("improved", chat.load(cid)["messages"][-1])

    def test_quality_waits_until_the_plan_is_finished(self):
        plan = '```plan\n[{"id":"p1","name":"Walls"},{"id":"p2","name":"Roof"}]\n```\n'
        ai = Ai(self, [([("build_step", {"code": BOX, "note": "box"})], plan + "Walls first.")])
        c = chat.create("A house")
        cid = ai.cid = c["id"]
        self.assertEqual(chat.run_turn(cid, "A house", add_user=False, log=lambda m: None)["rounds"], 0)   # no roof planned yet

    def test_pause_stops_the_rounds(self):
        stay = ([], "ok")
        ai = Ai(self, [([("build_step", {"code": BOX + FLOAT, "note": "plain"})], "Built."), stay, stay])
        c = chat.create("A house")
        cid = ai.cid = c["id"]
        orig = ai.spawn

        def spawn(cmd, work, env):
            proc = orig(cmd, work, env)
            if len(ai.cmds) == 2:
                chat.pause(cid)                      # the user presses Pause during round 1
            return proc
        with mock.patch.object(loop, "_spawn", spawn):
            res = chat.run_turn(cid, "A house", add_user=False, log=lambda m: None)
        self.assertEqual(res["rounds"], 1)
        self.assertEqual(len(ai.cmds), 2)
        self.assertIn("Paused while improving", chat.load(cid)["messages"][-1]["text"])
        self.assertNotIn(cid, chat._PAUSED)


class LazyProc(FakeProc):
    """An AI process that works on the session named in its message ("Session id: ...")."""

    def __init__(self, script, text):
        self.stdin = test_loop.io.BytesIO()
        self.stdin.close = lambda: None
        self.err_file = test_loop.io.BytesIO()
        self.script, self.text = script, text
        self.stdout = self._lazy()

    def _lazy(self):
        sid = re.search(r"Session id: (\w+)", self.stdin.getvalue().decode()).group(1)
        yield from self._play(sid, self.script, self.text)


class LoopSelfImprove(unittest.TestCase):
    def run_engine(self, later):
        first = [("start_build", {"title": "Cottage"}), ("build_step", {"session": "x", "code": COTTAGE + FLOAT, "note": "all"})]
        procs, lines = [], []

        def spawn(cmd, work, env):
            procs.append(cmd)
            if len(procs) == 1:
                return test_loop.FakeProc(first)
            script, text = later[len(procs) - 2]
            return LazyProc(script, text)
        with mock.patch.object(engine, "find_claude", return_value="claude"), mock.patch.object(loop, "_spawn", spawn), \
                mock.patch.object(loop, "newest_build", lambda *a, **k: None):
            meta = engine.generate("A cottage", size="small", engine="claude_loop", research=False, log=lines.append)
        return meta, procs, lines

    def test_extra_turn_fixes_the_build_before_saving(self):
        fix = ([("build_step", {"code": "clear(30,20,30,30,20,30)\n", "note": "remove floater"}), ("check", {}),
                ("save_build", {"title": "Cottage"})], "fixed")
        meta, procs, lines = self.run_engine([fix])
        self.assertEqual(len(procs), 2)
        self.assertIn("Improving: floating parts, round 1 of 2", lines)
        self.assertEqual(meta["checks"]["total"], 0)
        self.assertEqual(len([b for b in store.list_builds() if b["id"] == meta["id"]]), 1)

    def test_extra_turns_are_capped(self):
        meta, procs, lines = self.run_engine([([], "nothing"), ([], "nothing"), ([], "never used")])
        self.assertEqual(len(procs), 1 + selfimprove.LOOP_ROUNDS)
        self.assertEqual([l for l in lines if l.startswith("Improving:")],
                         [f"Improving: floating parts, round {k} of 2" for k in (1, 2)])
        self.assertTrue(meta["id"])                                      # still saved, as before (with its check results)
        self.assertEqual(meta["checks"]["total"], 1)

    def test_no_round_starts_when_the_time_is_used_up(self):
        with mock.patch.object(selfimprove, "LOOP_SECONDS", 0):
            meta, procs, lines = self.run_engine([([], "never used")])
        self.assertEqual(len(procs), 1)
        self.assertTrue(any(l.startswith("No time left for improvement round 1") for l in lines), lines)
        self.assertTrue(meta["id"])                                      # still saved, with its check results

    def test_prompt_states_the_rule(self):
        self.assertIn("check -> fix -> check", loop.system_prompt("x"))


class McpSelfImprove(unittest.TestCase):
    def test_bad_build_is_not_done_yet(self):
        out = mcp_server.call("create_build", {"code": BOX + FLOAT, "title": "Plain box"})
        self.assertTrue(out.startswith("NOT DONE YET - improve before you show the user:"), out[:200])
        self.assertIn("floating parts", out)
        self.assertRegex(out, r"\(30, 20, 30\)|30, 20, 30")                # coordinates of the floater
        self.assertIn(f"minimum is {quality.QUALITY_MIN}", out)
        self.assertIn("update_build", out)
        self.assertIn("check again", out)
        self.assertNotIn("Done", out.split("\n\n")[0])
        self.assertIn("Saved build", out)                                    # the id is there to call update_build with

    def test_clean_build_says_done(self):
        out = mcp_server.call("create_build", {"code": COTTAGE, "title": "Cottage"})
        self.assertTrue(out.startswith("Done. Saved build"), out[:200])
        self.assertNotIn("NOT DONE", out)

    def test_update_build_checks_again(self):
        bad = mcp_server.call("create_build", {"code": COTTAGE + FLOAT, "title": "Cottage"})
        self.assertTrue(bad.startswith("NOT DONE YET"))
        bid = re.search(r"\(id ([\w-]+)\)", bad).group(1)
        good = mcp_server.call("update_build", {"build_id": bid, "code": "fill(30,0,30,30,19,30,'stone')\n"})
        self.assertTrue(good.startswith("Done."), good[:300])

    def test_session_check_uses_the_same_words(self):
        sid = mcp_server.call("start_build", {"title": "t"}).split()[2]
        mcp_server.call("build_step", {"session": sid, "code": BOX + FLOAT})
        out = mcp_server.call("check", {"session": sid})
        self.assertTrue(out.startswith("NOT DONE YET - fix these"), out[:120])
        self.assertRegex(out, r"Checks: 1 problems")
        mcp_server.call("build_step", {"session": sid, "code": "clear(30,20,30,30,20,30)\n"})
        out = mcp_server.call("check", {"session": sid})
        self.assertTrue(out.startswith("No problems found"))
        self.assertIn("quality", out)                                        # clean checks but a plain box: said, not hidden
        self.assertIn("NOT DONE YET", out)

    def test_guide_tells_the_loop(self):
        guide = mcp_server.call("get_build_guide", {})
        self.assertIn("check -> fix -> check", guide)
        self.assertIn("never hand over", guide.lower().replace("Never hand over", "never hand over"))


if __name__ == "__main__":
    unittest.main()
