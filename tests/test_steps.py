"""The numbered launchers in steps/ must point at code that exists, and the numbers must be unique and in order."""

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEPS = sorted((ROOT / "steps").glob("[0-9][0-9]_*.py"))


class StepsTests(unittest.TestCase):
    def test_numbers_are_unique_and_consecutive(self):
        numbers = [int(p.name[:2]) for p in STEPS]
        self.assertEqual(numbers, list(range(len(numbers))))

    def test_every_launcher_points_at_existing_code(self):
        for path in STEPS:
            source = path.read_text(encoding="utf-8")
            module = re.search(r'^module\("([\w.]+)"\)', source, re.M)
            script = re.search(r'^script\("([^"]+)"\)', source, re.M)
            if module:
                self.assertIsNotNone(importlib.util.find_spec(module.group(1)), path.name)
            elif script:
                self.assertTrue((ROOT / script.group(1)).exists(), path.name)
            else:
                self.assertIn("streamlit", source, path.name)      # the dashboard launcher

    def test_readme_lists_every_step(self):
        readme = (ROOT / "steps" / "README.md").read_text(encoding="utf-8")
        for path in STEPS:
            self.assertIn(path.name, readme)


if __name__ == "__main__":
    unittest.main()
