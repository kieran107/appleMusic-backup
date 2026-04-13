#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_OUTPUT = Path.cwd() / "apple_music_songs.csv"
MUSIC_APP_PATH = "/System/Applications/Music.app"
FIELD_ALIASES = {
    "genre": "Genre",
    "grouping": "Grouping",
    "comments": "Comments",
    "work": "Work",
    "composer": "Composer",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export tracks from your Apple Music library to CSV with columns "
            "for song title, artist, album, and a custom category field."
        )
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--custom-field",
        choices=sorted(FIELD_ALIASES),
        default="genre",
        help=(
            "Which Music metadata field should be exported as the category column. "
            "Default: genre"
        ),
    )
    parser.add_argument(
        "--custom-header",
        default="类别",
        help='CSV column name for the custom field. Default: "类别"',
    )
    parser.add_argument(
        "--keep-xml",
        action="store_true",
        help="Keep the temporary Music XML export next to the CSV file.",
    )
    return parser.parse_args()


def export_music_library_xml(xml_path: Path) -> None:
    subprocess.run(
        ["open", "-a", MUSIC_APP_PATH],
        capture_output=True,
        text=True,
    )
    applescript = f"""
tell application "{MUSIC_APP_PATH}"
    launch
    delay 2
    export library playlist 1 to POSIX file "{escape_applescript_string(str(xml_path))}" as XML
end tell
"""
    result = subprocess.run(
        ["osascript", "-e", applescript],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and xml_path.exists():
        return

    message = result.stderr.strip() or result.stdout.strip() or "unknown osascript error"
    raise RuntimeError(
        "Failed to export the Music library XML.\n"
        f"Music returned: {message}\n\n"
        "Open Music.app once, make sure the library is available, and allow any "
        "Automation/Media permissions if macOS prompts you."
    )


def escape_applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def load_tracks_from_xml(xml_path: Path) -> list[dict[str, str]]:
    with xml_path.open("rb") as handle:
        library = plistlib.load(handle)

    tracks = library.get("Tracks", {})
    track_to_playlists = build_track_playlist_map(library.get("Playlists", []))
    rows: list[dict[str, str]] = []
    for track_key, track in tracks.items():
        name = clean_value(track.get("Name"))
        if not name:
            continue

        track_id = clean_value(track.get("Track ID")) or clean_value(track_key)
        rows.append(
            {
                "歌曲名": name,
                "歌手": clean_value(track.get("Artist")),
                "专辑": clean_value(track.get("Album")),
                "所在歌单": " | ".join(track_to_playlists.get(track_id, [])),
                "_genre": clean_value(track.get("Genre")),
                "_grouping": clean_value(track.get("Grouping")),
                "_comments": clean_value(track.get("Comments")),
                "_work": clean_value(track.get("Work")),
                "_composer": clean_value(track.get("Composer")),
            }
        )

    rows.sort(key=lambda row: (row["歌手"].casefold(), row["专辑"].casefold(), row["歌曲名"].casefold()))
    return rows


def clean_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_track_playlist_map(playlists: object) -> dict[str, list[str]]:
    if not isinstance(playlists, list):
        return {}

    playlist_index: dict[str, dict[object, object]] = {}
    for playlist in playlists:
        if not isinstance(playlist, dict):
            continue
        persistent_id = clean_value(playlist.get("Playlist Persistent ID"))
        if persistent_id:
            playlist_index[persistent_id] = playlist

    track_to_playlists: dict[str, set[str]] = {}
    for playlist in playlists:
        if not isinstance(playlist, dict) or not should_include_playlist(playlist):
            continue

        playlist_name = build_playlist_path(playlist, playlist_index)
        if not playlist_name:
            continue

        for item in playlist.get("Playlist Items", []):
            if not isinstance(item, dict):
                continue
            track_id = clean_value(item.get("Track ID"))
            if not track_id:
                continue
            track_to_playlists.setdefault(track_id, set()).add(playlist_name)

    return {
        track_id: sorted(names, key=str.casefold)
        for track_id, names in track_to_playlists.items()
    }


def should_include_playlist(playlist: dict[object, object]) -> bool:
    if not clean_value(playlist.get("Name")):
        return False

    if playlist.get("Folder") or playlist.get("Master"):
        return False

    if playlist.get("Distinguished Kind") is not None:
        return False

    special_flags = (
        "Music",
        "Movies",
        "TV Shows",
        "Podcasts",
        "Audiobooks",
        "Purchased Music",
    )
    return not any(playlist.get(flag) for flag in special_flags)


def build_playlist_path(
    playlist: dict[object, object],
    playlist_index: dict[str, dict[object, object]],
) -> str:
    parts = [clean_value(playlist.get("Name"))]
    parent_id = clean_value(playlist.get("Parent Persistent ID"))
    visited: set[str] = set()

    while parent_id and parent_id not in visited:
        visited.add(parent_id)
        parent = playlist_index.get(parent_id)
        if parent is None:
            break

        parent_name = clean_value(parent.get("Name"))
        if parent_name:
            parts.append(parent_name)
        parent_id = clean_value(parent.get("Parent Persistent ID"))

    return " / ".join(reversed([part for part in parts if part]))


def write_csv(rows: list[dict[str, str]], output_path: Path, custom_field: str, custom_header: str) -> None:
    key_name = f"_{custom_field}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["歌曲名", "歌手", "专辑", "所在歌单", custom_header])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "歌曲名": row["歌曲名"],
                    "歌手": row["歌手"],
                    "专辑": row["专辑"],
                    "所在歌单": row["所在歌单"],
                    custom_header: row.get(key_name, ""),
                }
            )


def main() -> int:
    args = parse_args()

    try:
        with tempfile.TemporaryDirectory(prefix="apple-music-export-") as temp_dir:
            xml_path = Path(temp_dir) / "music-library.xml"
            export_music_library_xml(xml_path)
            rows = load_tracks_from_xml(xml_path)
            write_csv(rows, args.output, args.custom_field, args.custom_header)

            if args.keep_xml:
                saved_xml = args.output.with_suffix(".xml")
                saved_xml.write_bytes(xml_path.read_bytes())

        print(f"Exported {len(rows)} tracks to {args.output}")
        if args.custom_field != "genre":
            print(
                "Category column source:",
                args.custom_field,
                f"(Apple Music field: {FIELD_ALIASES[args.custom_field]})",
            )
        return 0
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
