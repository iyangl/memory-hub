from __future__ import annotations

import argparse
from pathlib import Path

from mcp import MCPServer
from store import MemoryHubStore

DEFAULT_ROOT = Path.home() / ".memory-hub"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory Hub daemon (MVP)")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Storage root (default: ~/.memory-hub)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = MemoryHubStore(root_dir=args.root)
    server = MCPServer(store)
    server.run()


if __name__ == "__main__":
    main()
