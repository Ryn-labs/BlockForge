import unittest

from tests import _env  # noqa: F401
from blockforge import lessons


class Lessons(unittest.TestCase):
    def test_top(self):
        t = lessons.top()
        self.assertEqual(len(t), 40)
        self.assertEqual(len(lessons.top(5)), 5)
        self.assertEqual(lessons.top(0), [])
        self.assertTrue(all(len(x) > 15 for x in t))

    def test_styles(self):
        names = lessons.styles()
        for n in ("japanese", "medieval", "alpine", "modern", "fantasy", "desert", "nordic"):
            self.assertIn(n, names)
            text = lessons.for_style(n)
            self.assertIn("## Palette", text)
            self.assertIn("## Common mistakes", text)
            self.assertLess(len(text.splitlines()), 80)

    def test_lookup(self):
        self.assertEqual(lessons.for_style("Japanese"), lessons.for_style("japanese"))
        self.assertEqual(lessons.for_style("atlantean"), "")
        self.assertEqual(lessons.for_style(None), "")
        self.assertIn("torii", lessons.for_style("japanese"))
        self.assertIn("Reference", lessons.for_style("japanese"))

    def test_mistakes_count(self):
        for n in lessons.styles():
            block = lessons.for_style(n).split("## Common mistakes")[1].split("##")[0]
            self.assertGreaterEqual(sum(1 for ln in block.splitlines() if ln[:2].rstrip(".").isdigit()), 5, n)


if __name__ == "__main__":
    unittest.main()


class WiringTests(unittest.TestCase):
    def test_loop_prompt_has_lessons_and_style(self):
        from blockforge import loop
        p = loop.system_prompt("Build a castle. Palette: Medieval: stone bricks")
        self.assertIn("Lessons from earlier builds", p)
        self.assertIn("Style sheet: medieval", p)
        self.assertNotIn("Style sheet", loop.system_prompt("a plain hut"))
        self.assertIn("pattern", loop.TOOLS)

    def test_script_path_gets_lessons_short(self):
        from blockforge import engine
        t = engine._with_lessons(None, "claude_code")
        self.assertIn("Lessons from earlier builds", t)
        self.assertLess(len(t), 3200)
        self.assertEqual(engine._with_lessons("x", "claude_loop"), "x")

    def test_mcp_tools(self):
        from blockforge import mcp_server as m
        self.assertIn("Oak stairs", m.call("block_info", {"blocks": ["oak_stairs[facing=north]"]}))
        self.assertIn("Available", m.call("style_sheet", {"style": "nope"}))
        self.assertIn("medieval", m.call("style_sheet", {"style": "medieval"}).lower())
        self.assertTrue(m.call("lessons", {}).startswith("- "))
        self.assertIn("lantern_post(", m.call("pattern", {"name": "nope"}))
        self.assertIn("block(", m.call("pattern", {"name": "tree", "args": {"species": "oak", "x": 1, "y": 1, "z": 1}}))
