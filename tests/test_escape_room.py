"""Correctness tests. Run with:  python -m unittest -v

The checks themselves live in escape_room/checks.py, so the website's Testing page runs
exactly the same code in the browser."""
import re
import unittest

from escape_room.checks import CHECKS


class EscapeRoomTests(unittest.TestCase):
    ctx = {}  # shared between checks (the trained Q-learning lab is reused)


def _make(fn, proves):
    def test(self):
        passed, detail = fn(EscapeRoomTests.ctx)
        self.assertTrue(passed, detail)
    test.__doc__ = proves
    return test


for number, (group, name, proves, fn) in enumerate(CHECKS, 1):
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    setattr(EscapeRoomTests, f"test_{number:02d}_{slug}", _make(fn, proves))

if __name__ == "__main__":
    unittest.main()
