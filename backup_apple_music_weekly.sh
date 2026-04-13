#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPORT_SCRIPT="$SCRIPT_DIR/export_apple_music_library.py"
CSV_PATH="${CSV_PATH:-$SCRIPT_DIR/apple_music_songs.csv}"
CUSTOM_FIELD="${CUSTOM_FIELD:-genre}"
CUSTOM_HEADER="${CUSTOM_HEADER:-类别}"
STATE_FILE="${STATE_FILE:-$SCRIPT_DIR/.last_successful_backup_week}"
CURRENT_WEEK="$(date '+%G-W%V')"

if [[ ! -f "$EXPORT_SCRIPT" ]]; then
  echo "Missing exporter: $EXPORT_SCRIPT" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi

cd "$SCRIPT_DIR"

if [[ -f "$STATE_FILE" ]]; then
  last_week="$(<"$STATE_FILE")"
  if [[ "$last_week" == "$CURRENT_WEEK" ]]; then
    echo "Backup already completed for $CURRENT_WEEK. Skipping."
    exit 0
  fi
fi

python3 "$EXPORT_SCRIPT" \
  --output "$CSV_PATH" \
  --custom-field "$CUSTOM_FIELD" \
  --custom-header "$CUSTOM_HEADER"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "This folder is not a git repository yet." >&2
  echo "Run ./setup_apple_music_git_backup.sh <your-remote-url> first." >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Git remote 'origin' is not configured." >&2
  echo "Run ./setup_apple_music_git_backup.sh <your-remote-url> first." >&2
  exit 1
fi

git add "$CSV_PATH"

if git diff --cached --quiet; then
  echo "No CSV changes detected. Nothing to commit."
  printf '%s\n' "$CURRENT_WEEK" > "$STATE_FILE"
  exit 0
fi

current_branch="$(git branch --show-current)"
if [[ -z "$current_branch" ]]; then
  current_branch="main"
fi

timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "backup: apple music csv $timestamp"
git push origin "$current_branch"
printf '%s\n' "$CURRENT_WEEK" > "$STATE_FILE"
