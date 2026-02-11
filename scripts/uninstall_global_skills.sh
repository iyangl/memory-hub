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

for skill in "${SKILLS[@]}"; do
  src="$REPO_ROOT/skills/$skill"
  dst="$TARGET_DIR/$skill"

  if [[ -L "$dst" ]]; then
    target="$(readlink "$dst")"
    if [[ "$target" == "$src" ]]; then
      rm -f "$dst"
      echo "Removed: $dst"
    else
      echo "Skip (not this repo): $dst -> $target"
    fi
  elif [[ -e "$dst" ]]; then
    echo "Skip (not symlink): $dst"
  else
    echo "Skip (not found): $dst"
  fi
done

echo "Global skill uninstall complete."
echo "CODEX_HOME: $CODEX_HOME"
