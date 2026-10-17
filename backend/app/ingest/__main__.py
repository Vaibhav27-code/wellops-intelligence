from __future__ import annotations

import argparse
import json
from pathlib import Path

from .loader import DatasetValidationError, load_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and load a FlytBase-format dataset into SQLite")
    parser.add_argument("dataset", nargs="?", default="data/raw/flytbase-ahc-swe-asset-intelligence-dataset")
    parser.add_argument("--database", default="data/asset_intelligence.db")
    args = parser.parse_args()
    try:
        report = load_dataset(args.dataset, args.database)
    except DatasetValidationError as exc:
        print(json.dumps(exc.report.to_dict(), indent=2))
        return 2
    result = report.to_dict()
    result["database"] = str(Path(args.database).resolve())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
