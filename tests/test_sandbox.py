import unittest

from tests import _env  # noqa: F401
from blockforge import sandbox
from blockforge.engine import _overwrite_note


class OverwriteMeta(unittest.TestCase):
    def test_meta_reports_overwrites(self):
        _, meta = sandbox.run("fill(0,0,0,9,0,9,'stone')\nfill(0,0,0,4,0,4,'dirt')\nfill(0,0,0,4,0,4,'dirt')\n")
        self.assertEqual(meta["overwrites"]["count"], 25)
        self.assertEqual(len(meta["overwrites"]["examples"]), 20)
        self.assertIn("25", _overwrite_note(meta))

    def test_no_overwrites_no_note(self):
        _, meta = sandbox.run("fill(0,0,0,3,0,3,'stone')\n")
        self.assertEqual(meta["overwrites"]["count"], 0)
        self.assertEqual(_overwrite_note(meta), "")


if __name__ == "__main__":
    unittest.main()
