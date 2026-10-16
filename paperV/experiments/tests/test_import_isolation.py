"""paperV.experiments.filter imports as a namespace package next to Paper I's flat `constants`."""
import subprocess
import sys

import constants as C

CODE = r"""
import importlib, sys
sys.path.insert(0, {repo!r}); sys.path.insert(0, {p1!r})
import constants as p1c
assert p1c.__file__.endswith('paperI/experiments/constants.py'), p1c.__file__
f = importlib.import_module('paperV.experiments.filter')
assert f.C.__file__.endswith('paperV/experiments/constants.py'), f.C.__file__
assert sys.modules['constants'] is p1c
pl = importlib.import_module('paperV.experiments.plant')
assert pl.C is f.C
print('ok')
"""


def test_namespace_import():
    code = CODE.format(repo=str(C.REPO), p1=str(C.REPO / "paperI" / "experiments"))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd="/")
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr[-3000:]
