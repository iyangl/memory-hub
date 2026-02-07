from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from store import MemoryHubStore

DEFAULT_ROOT = Path.home() / ".memory-hub"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backup a project database")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--project-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file or directory (default: ./backups)",
    )
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    args = parse_args()
    store = MemoryHubStore(root_dir=args.root)
    db_path = store.db_path(args.project_id)
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")

    if args.output is None:
        backup_dir = Path.cwd() / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        dest = backup_dir / f"{args.project_id}_{_timestamp()}.db"
    else:
        output = args.output
        if output.exists() and output.is_dir():
            dest = output / f"{args.project_id}_{_timestamp()}.db"
        elif output.suffix:
            output.parent.mkdir(parents=True, exist_ok=True)
            dest = output
        else:
            output.mkdir(parents=True, exist_ok=True)
            dest = output / f"{args.project_id}_{_timestamp()}.db"

    shutil.copy2(db_path, dest)
    print(dest)


if __name__ == "__main__":
    main()
