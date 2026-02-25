"""CLI dispatcher for memory-hub commands."""

from __future__ import annotations

import sys

from lib.envelope import system_error

COMMANDS = {
    "init": "lib.memory_init",
    "read": "lib.memory_read",
    "list": "lib.memory_list",
    "search": "lib.memory_search",
    "write": "lib.memory_write",
    "catalog-read": "lib.catalog_read",
    "catalog-update": "lib.catalog_update",
    "catalog-repair": "lib.catalog_repair",
}


def main() -> None:
    if len(sys.argv) < 2:
        system_error(f"Usage: memory-hub <command> [args]\nCommands: {', '.join(COMMANDS)}")

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        system_error(f"Unknown command: {cmd}\nAvailable: {', '.join(COMMANDS)}")

    # Dynamic import to avoid loading all modules upfront
    import importlib
    module = importlib.import_module(COMMANDS[cmd])
    module.run(sys.argv[2:])


if __name__ == "__main__":
    main()
