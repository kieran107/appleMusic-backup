#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.zzh.apple-music-weekly-backup.plist"
SOURCE_PLIST="$SCRIPT_DIR/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"
SERVICE_ID="gui/$(id -u)/com.zzh.apple-music-weekly-backup"

if [[ ! -f "$SOURCE_PLIST" ]]; then
  echo "Missing plist template: $SOURCE_PLIST" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
cp "$SOURCE_PLIST" "$TARGET_PLIST"

launchctl bootout "$SERVICE_ID" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET_PLIST"
launchctl enable "$SERVICE_ID"

echo "Installed weekly launch agent:"
echo "  $TARGET_PLIST"
echo "Schedule: Tuesday to Thursday at 20:00, once per week after the first successful run"
