"""Backend package; also supports ``app.*`` imports when launched from backend/."""

from pathlib import Path
import sys


if __name__ == "app":
    project_root = str(Path(__file__).resolve().parents[2])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
