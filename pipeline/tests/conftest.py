import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for path in (REPO / "pipeline", REPO / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
