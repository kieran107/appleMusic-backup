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
    rows: list[dict[str, str]] = []
    for track in tracks.values():
        name = clean_value(track.get("Name"))
        if not name:
            continue

        rows.append(
            {
                "歌曲名": name,
                "歌手": clean_value(track.get("Artist")),
                "专辑": clean_value(track.get("Album")),
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


def write_csv(rows: list[dict[str, str]], output_path: Path, custom_field: str, custom_header: str) -> None:
    key_name = f"_{custom_field}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["歌曲名", "歌手", "专辑", custom_header])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "歌曲名": row["歌曲名"],
                    "歌手": row["歌手"],
                    "专辑": row["专辑"],
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
