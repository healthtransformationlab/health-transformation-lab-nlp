# Added so the competition's evaluator can import this repository's package, which lives in python/.
# The evaluator puts the repository root on the import path; this puts python/ there too, for the tests and for
# any script a test starts.
import os
import sys
from pathlib import Path

_PKG = str(Path(__file__).resolve().parent / "python")
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)
os.environ["PYTHONPATH"] = os.pathsep.join(
    [_PKG] + [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p and p != _PKG])
