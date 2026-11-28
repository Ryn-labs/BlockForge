"""Script engine: after the check-fix round a building below quality.QUALITY_MIN gets one quality fix round; the new
version is kept only if it scores higher, and the score is saved in meta["quality"]."""
import unittest
from unittest import mock

from tests import _env  # noqa: F401
from blockforge import engine, examples, prompts, quality

BOX = ("fill(0,0,0,8,0,8,'cobblestone')\nwalls(0,1,0,8,4,8,'cobblestone')\nfill(0,5,0,8,5,8,'cobblestone')\n"
       "block(4,1,8,B('oak_door',facing='south',half='lower'))\nblock(4,2,8,B('oak_door',facing='south',half='upper'))\n"
       "block(4,4,4,B('lantern',hanging=True))\n")                  # lit inside: plain, but no check problem


def fake(first, second):
    class Conv:
        follow_ups = []

        def __init__(self, *a, **k):
            pass

        def first(self):
            return f"Box\n```python\n{first}```"

        def follow_up(self, message, code):
            Conv.follow_ups.append(message)
            return f"Box\n```python\n{second}```"
    return Conv


def run(conv):
    lines = []
    no_size = mock.patch.object(prompts, "size_error", lambda size, dims: (0, None))   # only the quality round here
    with mock.patch.object(engine, "_Conversation", conv), no_size:
        meta = engine.generate("A cottage", size="", engine="claude_code", build_mode="script", research=False,
                               use_mods=False, log=lines.append)
    return meta, "\n".join(lines)


class QualityRound(unittest.TestCase):
    def test_plain_box_gets_one_quality_round_and_keeps_the_better_build(self):
        conv = fake(BOX, examples.code("good_cottage"))
        meta, log = run(conv)
        self.assertEqual(len(conv.follow_ups), 1)
        self.assertIn("quality check scores this building", conv.follow_ups[0])
        self.assertIn("Weakest parts", conv.follow_ups[0])
        self.assertGreaterEqual(meta["quality"]["total"], 70)
        self.assertIn("Quality after the fix", log)

    def test_a_worse_answer_is_not_kept(self):
        conv = fake(BOX, BOX.replace("cobblestone", "dirt"))
        meta, log = run(conv)
        self.assertLess(meta["quality"]["total"], quality.QUALITY_MIN)
        self.assertIn("Kept the first version", log)
        self.assertGreater(meta["block_count"], 250)

    def test_a_good_build_gets_no_quality_round(self):
        conv = fake(examples.code("good_cottage"), BOX)
        meta, log = run(conv)
        self.assertEqual([m for m in conv.follow_ups if "quality check" in m], [])
        self.assertGreaterEqual(meta["quality"]["total"], 70)

    def test_message_lists_the_weakest_parts(self):
        from blockforge import sandbox
        q = quality.score(sandbox.run_safe(BOX)[0])
        msg = prompts.quality_fix_message(q)
        self.assertEqual(len([ln for ln in msg.splitlines() if ln.startswith("- ") and "/100" in ln]), 3)
        self.assertIn("```python", msg)


if __name__ == "__main__":
    unittest.main()
