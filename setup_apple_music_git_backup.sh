#!/bin/zsh

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <git-remote-url>" >&2
  exit 1
fi

REMOTE_URL="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -b main
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

git add export_apple_music_library.py backup_apple_music_weekly.sh setup_apple_music_git_backup.sh install_apple_music_launch_agent.sh com.zzh.apple-music-weekly-backup.plist

if [[ -f apple_music_songs.csv ]]; then
  git add apple_music_songs.csv
fi

if git diff --cached --quiet; then
  echo "Nothing new to commit."
else
  git commit -m "setup: apple music weekly backup"
fi

git push -u origin main
