"""Run a registered unittest module and verify that its named source cases passed."""

import importlib
import json
import sys
import unittest
from pathlib import Path


class OriginResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_ids = set()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_ids.add(test.id())


def run(path, cases):
    sys.path.insert(0, str(path.parent))
    module = importlib.import_module(path.stem)
    if Path(module.__file__).resolve() != path.resolve():
        raise ValueError(f"origin suite did not load its registered module: {path}")
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(resultclass=OriginResult).run(suite)
    missing = {origin: case for origin, case in cases.items()
               if f"{module.__name__}.{case}" not in result.passed_ids}
    if missing:
        print(f"source cases without a successful execution: {missing}", file=sys.stderr)
    return result.wasSuccessful() and not missing


if __name__ == "__main__":
    sys.exit(0 if run(Path(sys.argv[1]), json.loads(sys.argv[2])) else 1)
