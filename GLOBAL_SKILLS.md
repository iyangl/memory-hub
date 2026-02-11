# Global Skills Setup

This project provides three skills:
- `memory-pull`
- `memory-push`
- `memory-sync` (combined start/finish entry)

## Install to global Codex skills

```bash
cd /Users/sunpure/Documents/Code/memory-hub
chmod +x scripts/install_global_skills.sh scripts/uninstall_global_skills.sh
./scripts/install_global_skills.sh
```

Optional custom Codex home:

```bash
CODEX_HOME=/path/to/.codex ./scripts/install_global_skills.sh
```

## Verify install

```bash
ls -la ~/.codex/skills/memory-pull
ls -la ~/.codex/skills/memory-push
ls -la ~/.codex/skills/memory-sync
```

## Usage in chat

Start a new session task:

```text
[$memory-sync](~/.codex/skills/memory-sync/SKILL.md) start <your task prompt>
```

or explicit pull:

```text
[$memory-pull](~/.codex/skills/memory-pull/SKILL.md) <your task prompt>
```

Finish and sync:

```text
[$memory-sync](~/.codex/skills/memory-sync/SKILL.md) finish
```

or explicit push:

```text
[$memory-push](~/.codex/skills/memory-push/SKILL.md)
```

## Uninstall

```bash
cd /Users/sunpure/Documents/Code/memory-hub
./scripts/uninstall_global_skills.sh
```

## Notes
- Skills are installed as symlinks, so updates in this repo are reflected globally.
- If skills do not appear, restart the Codex session.
