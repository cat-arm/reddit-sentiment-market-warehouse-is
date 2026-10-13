"""Shared launcher for the numbered steps: puts the project root on sys.path and runs the real module or script,
passing the command-line arguments through.  (The real code keeps its module names, so imports and tests still work;
python cannot import a module whose name starts with a digit, which is why the numbers live in these launchers.)"""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def module(name):
    """Same as `python -m <name> <args>` from the project root."""
    runpy.run_module(name, run_name="__main__", alter_sys=True)


def script(relative_path):
    """Same as `python <relative_path> <args>` from the project root."""
    path = ROOT / relative_path
    sys.argv[0] = str(path)
    runpy.run_path(str(path), run_name="__main__")
