import io
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from tests import _env  # noqa: F401
from blockforge import chat, engine, loop, mcp_server, server, session, store

FLOOR = "fill(0,0,0,19,0,19,'stone_bricks')\n"
WALLS = "fill(0,1,0,19,5,19,'oak_planks', hollow=True)\n"
PLAN = '```plan\n[{"id":"p1","name":"Ground floor"},{"id":"p2","name":"Walls"},{"id":"p3","name":"Roof"}]\n```\n'
QUESTIONS = ('Quick questions first.\n```questions\n[{"id":"size","text":"How big?","choices":["About 100x100","200x200","Bigger"]},'
             '{"id":"on","text":"Build on:","choices":["Flat ground","My terrain (.schem)"]}]\n```')


class FakeProc:
    """Stands in for claude.exe: runs the tool calls on the real session tools, then answers with `text`."""

    def __init__(self, sid, script, text):
        self.stdin = io.BytesIO()
        self.err_file = io.BytesIO()
        self.stdout = self._play(sid, script, text)

    def _play(self, sid, script, text):
        n = 0
        for name, args in script:
            n += 1
            args = dict(args, session=sid)
            yield json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"t{n}", "name": "mcp__blockforge__" + name, "input": args}]}}).encode() + b"\n"
            out = mcp_server.handle({"method": "tools/call", "id": n, "params": {"name": name, "arguments": args}})
            yield json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"t{n}", "content": out["content"],
                 "is_error": bool(out.get("isError"))}]}}).encode() + b"\n"
        yield json.dumps({"type": "result", "is_error": False, "result": text, "num_turns": n, "duration_ms": 10,
                          "total_cost_usd": 0.01, "modelUsage": {}}).encode() + b"\n"

    def wait(self):
        return 0

    def kill(self):
        pass


class Ai:
    """A queue of (tool calls, final text) replies standing in for the AI process of each turn."""

    def __init__(self, test_case, replies):
        self.replies, self.cmds, self.procs, self.cid = list(replies), [], [], None
        self.patches = [mock.patch.object(engine, "find_claude", return_value="claude"), mock.patch.object(loop, "_spawn", self.spawn)]
        for p in self.patches:
            p.start()
            test_case.addCleanup(p.stop)

    def spawn(self, cmd, work, env):
        self.cmds.append(cmd)
        script, text = self.replies.pop(0)
        proc = FakeProc(chat.load(self.cid)["session"], script, text)
        proc.stdin.close = lambda: None
        self.procs.append(proc)
        return proc

    @property
    def users(self):
        return [p.stdin.getvalue().decode() for p in self.procs]


class ChatFlow(unittest.TestCase):
    def test_full_flow(self):
        ai = Ai(self, [
            ([], QUESTIONS),
            ([("build_step", {"code": FLOOR, "note": "floor"}), ("check", {})],
             PLAN + 'Floor is down.\n```status\n{"done":["p1"],"title":"Stone hall"}\n```'),
            ([("build_step", {"code": WALLS, "note": "walls"})], "Walls up."),                      # no status block
            ([("build_step", {"code": "replace(0,1,0,19,5,19,'oak_planks','spruce_planks')\n"
                                      "fill(60,0,60,60,0,60,'stone')\n", "note": "tweak"})], "Walls are spruce now."),
        ])
        c = chat.create("A stone hall", size="medium")
        cid = ai.cid = c["id"]
        self.assertEqual(c["head"], "v1")
        # questions come back as choices and nothing is built
        self.assertIsNone(chat.run_turn(cid, "A stone hall", add_user=False)["version"])
        c = chat.load(cid)
        qs = c["messages"][-1]["questions"]
        self.assertEqual([q["id"] for q in qs], ["size", "on"])
        self.assertEqual(qs[0]["choices"], ["About 100x100", "200x200", "Bigger"])
        self.assertNotIn("```", c["messages"][-1]["text"])
        cmd = ai.cmds[0]
        self.assertIn("mcp__blockforge__build_step", cmd[cmd.index("--allowedTools") + 1])
        self.assertNotIn("mcp__blockforge__save_build", cmd[cmd.index("--allowedTools") + 1])
        self.assertIn("Chat rules", cmd[cmd.index("--system-prompt") + 1])
        self.assertIn("Session id: " + c["session"], ai.users[0])
        # answers: the turn starts only after the last one
        self.assertIsNone(chat.answer(cid, "size", "200x200"))
        text = chat.answer(cid, "on", "Flat ground")
        self.assertIn("200x200", text)
        with self.assertRaises(chat.ChatError):
            chat.answer(cid, "on", "Flat ground")
        # plan parsed, part 1 built, version recorded
        self.assertEqual(chat.run_turn(cid, text, add_user=False)["version"], "v2")
        c = chat.load(cid)
        self.assertEqual([p["name"] for p in c["plan"]], ["Ground floor", "Walls", "Roof"])
        self.assertEqual([p["status"] for p in c["plan"]], ["done", "pending", "pending"])
        self.assertEqual(c["plan"][0]["bbox"], [0, 0, 0, 19, 0, 19])
        self.assertEqual(c["title"], "Stone hall")
        self.assertEqual(c["versions"][-1]["added"], 400)
        # the next part (no status block: the first open part)
        self.assertEqual(chat.run_turn(cid, "continue")["version"], "v3")
        c = chat.load(cid)
        self.assertEqual([p["status"] for p in c["plan"]], ["done", "done", "pending"])
        self.assertEqual(c["plan"][1]["bbox"][1], 1)
        before = session.load(c["session"]).blocks
        # a scoped change only touches the part's box; the stray block outside is put back
        self.assertEqual(chat.run_turn(cid, "make the walls spruce", part_id="p2")["version"], "v4")
        c = chat.load(cid)
        after = session.load(c["session"]).blocks
        box = chat.scope_box(c["plan"][1])
        self.assertNotIn((60, 0, 60), after)
        self.assertEqual(c["versions"][-1]["kept_outside"], 1)
        for p in set(before) | set(after):
            if not chat._inside(p, box):
                self.assertEqual(before.get(p), after.get(p), p)
        self.assertEqual(after[(0, 2, 0)], "minecraft:spruce_planks")
        self.assertEqual(c["messages"][-1]["change"]["part"], "Walls")
        self.assertIn("Scope: part p2", ai.users[-1])
        self.assertEqual(c["messages"][-2]["scope"]["name"], "Walls")
        self.assertGreater(chat.compare(cid, "v3")["changed"], 0)
        # undo goes back one version and keeps the history
        self.assertEqual(chat.undo(cid)["head"], "v3")
        self.assertEqual(session.load(c["session"]).blocks, before)
        h = chat.history(cid)["versions"]
        self.assertEqual(len(h), 4)
        self.assertFalse(next(x for x in h if x["id"] == "v4")["on_path"])
        # checkout makes a branch with its own session; the old one is untouched
        old_sid = c["session"]
        v = chat.checkout(cid, "v2")
        self.assertEqual(v["branch"], "b2")
        self.assertNotEqual(v["session"], old_sid)
        self.assertEqual(len(session.load(v["session"]).blocks), 400)
        self.assertEqual(session.load(old_sid).blocks, before)
        self.assertEqual([p["status"] for p in v["plan"]], ["done", "pending", "pending"])
        self.assertEqual(chat.history(cid)["versions"][0]["parent"], "v2")
        # save
        out = chat.save_build(cid)
        self.assertEqual(store.get_meta(out["id"])["block_count"], 400)
        self.assertIn("share", out)

    def test_parser_is_forgiving(self):
        self.assertEqual(chat.parse_reply("Hello there"), ("Hello there", None, None, None))
        clean, q, plan, _ = chat.parse_reply('x\n```plan\nnot json at all\n```\n```questions\n[{"text":"Q?","choices":["a","b"]}]\n```')
        self.assertIsNone(plan)
        self.assertEqual(q[0]["id"], "q1")
        self.assertEqual(clean, "x")
        _, _, plan, _ = chat.parse_reply('```plan\n["Terrain", "Walls"]\n```')
        self.assertEqual([p["id"] for p in plan], ["p1", "p2"])
        _, q, _, _ = chat.parse_reply("```questions\n" + json.dumps([{"text": f"q{i}", "choices": ["a"]} for i in range(5)]) + "\n```")
        self.assertEqual(len(q), 3)

    def test_terrain_start(self):
        m = store.save_build({(x, 0, z): "minecraft:grass_block" for x in range(5) for z in range(5)}, "Terrain", source="import")
        c = chat.create("A hut", terrain_build_id=m["id"])
        self.assertEqual(len(session.load(c["session"]).blocks), 25)
        self.assertEqual(chat.view(c["id"])["info"]["blocks"], 25)

    def test_pause_keeps_the_work_so_far(self):
        c = chat.create("A hall")
        cid = c["id"]
        stopped = threading.Event()

        class Slow(FakeProc):
            def _play(self, sid, script, text):
                yield from super()._play(sid, script, None)
                stopped.wait(10)                        # still "working" until Pause kills it

            def kill(self):
                stopped.set()
        slow = Slow(c["session"], [("build_step", {"code": FLOOR, "note": "floor"})], None)
        # the result line is never reached: the generator ends after kill without one
        slow.stdout = (l for l in slow.stdout if b'"result"' not in l)
        with mock.patch.object(engine, "find_claude", return_value="claude"), mock.patch.object(loop, "_spawn", lambda *a: slow):
            t = threading.Thread(target=lambda: chat.run_turn(cid, "A hall", add_user=False, log=lambda m: None))
            t.start()
            for _ in range(100):
                if cid in chat._PROCS:
                    break
                time.sleep(0.05)
            time.sleep(0.3)
            chat.pause(cid)
            t.join(10)
        self.assertFalse(t.is_alive())
        c = chat.load(cid)
        self.assertEqual(c["head"], "v2")
        self.assertIn("Paused", c["messages"][-1]["text"])
        with self.assertRaises(chat.ChatError):
            chat.pause(cid)

    def test_failed_turn_is_reported(self):
        c = chat.create("x")
        with mock.patch.object(engine, "find_claude", return_value=None):
            with self.assertRaises(engine.EngineError):
                chat.run_turn(c["id"], "x", add_user=False)
        self.assertNotIn(c["id"], chat._BUSY)
        self.assertTrue(chat.load(c["id"])["messages"][-1].get("error"))


COTTAGE_WALLS = ("fill(0,0,0,10,0,8,'cobblestone')\n"
                 "walls(0,1,0,10,4,8,'oak_planks')\n"
                 "fill(0,5,0,10,5,8,'spruce_planks')\n"
                 "block(5,1,8,B('oak_door',facing='south',half='lower'))\n"
                 "block(5,2,8,B('oak_door',facing='south',half='upper'))\n")
PARTS_REPLY = ("I've built the plot and the cottage body.\n\nNext is part 2: a steep gable roof in red or green with an "
               "oak trim, and a chimney.")


class ChatPlanCard(unittest.TestCase):
    """The plan card always shows for a build in parts, and improvement rounds keep the plan and the next step true."""

    def test_derive_plan_from_the_parts_named(self):
        plan = chat.derive_plan(PARTS_REPLY)
        self.assertEqual([p["id"] for p in plan], ["p1", "p2", "p3", "p4"])
        self.assertEqual(plan[0]["name"], "Base and walls")
        self.assertTrue(plan[1]["name"].startswith("Steep gable roof in red or green"))
        self.assertEqual([p["name"] for p in plan[2:]], ["Windows and details", "Garden and path"])
        self.assertIsNone(chat.derive_plan("Built the house."))         # one part, nothing next: no card forced
        six = chat.derive_plan("Part 1: walls. Part 6: a tower.")
        self.assertEqual(len(six), 6)
        self.assertEqual(six[5]["name"], "Tower")
        self.assertEqual(chat.next_line(plan), "Next is part 1: base and walls.")
        self.assertEqual(chat.next_line([dict(p, status="done") for p in plan]), "Every part of the plan is done.")

    def test_card_shows_when_the_reply_has_no_plan_block(self):
        ai = Ai(self, [([("build_step", {"code": COTTAGE_WALLS, "note": "body"})], PARTS_REPLY)])
        c = chat.create("A small timber cottage with a garden.", size="small")
        cid = ai.cid = c["id"]
        chat._one_turn(cid, "A small timber cottage with a garden.", None, lambda m: None, False)
        c = chat.load(cid)
        self.assertEqual(len(c["plan"]), 4)
        self.assertEqual([p["status"] for p in c["plan"]], ["done", "pending", "pending", "pending"])
        self.assertEqual(c["plan"][0]["bbox"][0], 0)
        self.assertTrue(chat.view(cid)["plan"])

    def test_improve_round_marks_parts_done_and_the_next_line_follows(self):
        from blockforge import examples
        cottage = "clear(-10,-10,-10,80,80,80)\n" + examples.code("good_cottage")
        ai = Ai(self, [([("build_step", {"code": COTTAGE_WALLS + "block(30,20,30,'stone')\n", "note": "body"})],
                        PARTS_REPLY),
                       ([("build_step", {"code": cottage, "note": "better"}), ("check", {})], "Fixed it.")])
        c = chat.create("A small timber cottage with a garden.", size="small")
        cid = ai.cid = c["id"]
        res = chat.run_turn(cid, "A small timber cottage with a garden.", add_user=False, log=lambda m: None)
        self.assertEqual(res["rounds"], 1)
        c = chat.load(cid)
        self.assertEqual([p["status"] for p in c["plan"]], ["done"] * 4)   # the round built the roof, windows, garden
        texts = [m["text"] for m in c["messages"] if m["role"] == "ai"]
        self.assertFalse(any("Next is part 2" in t for t in texts), texts)
        self.assertIn("Every part of the plan is done.", texts[0])
        self.assertIn("That also built steep gable roof", texts[-1])
        self.assertTrue(texts[-1].endswith("Every part of the plan is done."))
        self.assertEqual(c["next"], "Every part of the plan is done.")

    def test_covered_reads_the_blocks(self):
        from blockforge import examples, sandbox
        walls = sandbox.run_safe(COTTAGE_WALLS)[0]
        full = sandbox.run_safe(examples.code("good_cottage"))[0]
        self.assertTrue(chat.covered("Base and walls", walls))
        self.assertFalse(chat.covered("A steep gable roof and a chimney", walls))
        self.assertTrue(chat.covered("A steep gable roof and a chimney", full))
        self.assertTrue(chat.covered("Garden and path", full))
        self.assertFalse(chat.covered("Garden and path", walls))
        self.assertFalse(chat.covered("Something else", full))           # unknown words are never guessed


class ChatRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 8799), server.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def call(self, method, path, body=None):
        req = urllib.request.Request("http://127.0.0.1:8799/api/" + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def wait(self, job):
        for _ in range(150):
            j = self.call("GET", "jobs/" + job)[1]
            if j["status"] != "running":
                return j
            time.sleep(0.1)
        self.fail("job did not finish")

    def test_routes(self):
        ai = Ai(self, [
            ([], QUESTIONS.replace('"on"', '"base"')),
            ([("build_step", {"code": FLOOR, "note": "floor"})], PLAN + "Floor done."),
            ([("build_step", {"code": WALLS, "note": "walls"})], "Walls."),
        ])
        self.assertEqual(self.call("POST", "chat/start", {"prompt": "  "})[0], 400)
        r = self.call("POST", "chat/start", {"prompt": "A hall", "size": "medium"})[1]
        cid = ai.cid = r["chat_id"]
        self.assertEqual(self.wait(r["job"])["status"], "done")
        code, st = self.call("GET", "chat/" + cid)
        self.assertEqual(code, 200)
        self.assertEqual(st["messages"][-1]["questions"][0]["choices"][1], "200x200")
        self.assertFalse(st["busy"])
        self.assertNotIn("snapshot", json.dumps(st))
        self.assertIsNone(self.call("POST", f"chat/{cid}/answer", {"question_id": "size", "choice": "200x200"})[1]["job"])
        r = self.call("POST", f"chat/{cid}/answer", {"question_id": "base", "choice": "Flat ground"})[1]
        self.assertEqual(self.wait(r["job"])["status"], "done")
        st = self.call("GET", "chat/" + cid)[1]
        self.assertEqual(st["plan"][0]["status"], "done")
        self.assertEqual(st["info"]["blocks"], 400)
        r = self.call("POST", f"chat/{cid}/message", {"text": "go on"})[1]
        self.assertEqual(self.wait(r["job"])["status"], "done")
        self.assertEqual(self.call("POST", f"chat/{cid}/message", {"text": " "})[0], 400)
        h = self.call("GET", f"chat/{cid}/history")[1]
        self.assertEqual([v["id"] for v in h["versions"]], ["v3", "v2", "v1"])
        self.assertEqual(self.call("GET", f"chat/{cid}/blocks")[1]["size"], [20, 6, 20])
        cmp = self.call("GET", f"chat/{cid}/compare?version=v2")[1]
        self.assertGreater(cmp["added"], 0)
        self.assertEqual(self.call("POST", f"chat/{cid}/undo", {})[1]["head"], "v2")
        self.assertEqual(self.call("POST", f"chat/{cid}/keep", {"version": "v2"})[1]["versions"][1]["kept"], True)
        self.assertEqual(self.call("POST", f"chat/{cid}/checkout", {"version": "v1"})[1]["branch"], "b2")
        self.assertEqual(self.call("POST", f"chat/{cid}/save", {})[0], 400)          # v1 is empty: nothing to save
        self.assertEqual(self.call("POST", f"chat/{cid}/checkout", {"version": "v2"})[1]["branch"], "b3")
        code, r = self.call("POST", f"chat/{cid}/save", {"title": "My hall"})
        self.assertEqual(code, 200)
        self.assertEqual(store.get_meta(r["id"])["title"], "My hall")
        self.assertEqual(self.call("GET", "chat/ffffffffff")[0], 404)
        self.assertIn(cid, [c["id"] for c in self.call("GET", "chats")[1]])


if __name__ == "__main__":
    unittest.main()
