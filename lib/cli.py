"""CLI dispatcher for memory-hub commands."""

from __future__ import annotations

import sys

from lib.envelope import system_error

COMMANDS = {
    "init": "lib.memory_init",
    "read": "lib.memory_read",
    "list": "lib.memory_list",
    "search": "lib.memory_search",
    "index": "lib.memory_index",
    "catalog-read": "lib.catalog_read",
    "catalog-update": "lib.catalog_update",
    "catalog-repair": "lib.catalog_repair",
    "brief": "lib.brief",
    "scan-modules": "lib.scan_modules",
    "recall-plan": "lib.recall_planner",
    "working-set": "lib.session_working_set",
    "execution-contract": "lib.execution_contract",
    "save": "lib.memory_save",
    "inbox-list": "lib.inbox_list",
    "inbox-clean": "lib.inbox_clean",
    "modules-check": "lib.modules_check",
}


def main() -> None:
    if len(sys.argv) < 2:
        system_error(f"Usage: memory-hub <command> [args]\nCommands: {', '.join(COMMANDS)}")

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        system_error(f"Unknown command: {cmd}\nAvailable: {', '.join(COMMANDS)}")

    import importlib
    module = importlib.import_module(COMMANDS[cmd])
    module.run(sys.argv[2:])


if __name__ == "__main__":
    main()
