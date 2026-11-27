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
