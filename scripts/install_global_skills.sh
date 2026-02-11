#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
TARGET_DIR="$CODEX_HOME/skills"

SKILLS=(
  "memory-pull"
  "memory-push"
  "memory-sync"
)

mkdir -p "$TARGET_DIR"

for skill in "${SKILLS[@]}"; do
  src="$REPO_ROOT/skills/$skill"
  dst="$TARGET_DIR/$skill"
  if [[ ! -d "$src" ]]; then
    echo "Missing skill directory: $src" >&2
    exit 1
  fi
  ln -sfn "$src" "$dst"
  echo "Installed: $skill -> $dst"
done

echo "Global skill install complete."
echo "CODEX_HOME: $CODEX_HOME"
