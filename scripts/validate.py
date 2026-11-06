#!/usr/bin/env python3
"""Checks index.json and every .wbmm file with the same rules as WidgetBlocks (MusicMood.swift).

Run from the repository root: python3 scripts/validate.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOODS = {"neutral", "calm", "happy", "sad", "hype", "anger", "intense"}
HINTS = {"dominant", "lightest", "darkest", "vivid"}
MAX_BYTES = 64 * 1024


def lookup_key(artist: str, title: str) -> str:
    """Same as MusicMoodFile.lookupKey(artist:title:) in the app."""
    def clean(text: str) -> str:
        without_brackets = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", text)
        return "".join(ch for ch in without_brackets.lower() if ch.isalnum())
    return f"{clean(artist)}|{clean(title)}"


def seconds(text: str):
    fields = text.split(":")
    if len(fields) not in (2, 3) or not all(f.isdigit() for f in fields):
        return None
    values = [int(f) for f in fields]
    if any(v >= 60 for v in values[1:]):
        return None
    total = 0
    for v in values:
        total = total * 60 + v
    return total


def parse(text: str):
    """Returns (headers, sections) or raises ValueError, mirroring MusicMoodFile.parse."""
    headers, sections = {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            for part in line.split("]"):
                body = part.strip()
                if not body:
                    continue
                if not body.startswith("["):
                    raise ValueError(f"expected a section like [calm 0:00-1:30], found “{body}”")
                fields = body[1:].split()
                if len(fields) not in (2, 3):
                    raise ValueError(f"“[{body[1:]}]” should be [mood start-end] or [mood start-end hint]")
                mood = fields[0].lower()
                if mood not in MOODS:
                    raise ValueError(f"unknown mood “{fields[0]}”; use one of {', '.join(sorted(MOODS))}")
                times = fields[1].split("-")
                start = seconds(times[0]) if len(times) == 2 else None
                end = seconds(times[1]) if len(times) == 2 else None
                if start is None or end is None:
                    raise ValueError(f"“{fields[1]}” isn't a time range like 0:00-1:30")
                if end <= start:
                    raise ValueError(f"“{fields[1]}” ends before it starts")
                if len(fields) == 3 and fields[2].lower() not in HINTS:
                    raise ValueError(f"unknown hint “{fields[2]}”; use one of {', '.join(sorted(HINTS))}")
                sections.append((start, end))
        elif ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    if not headers.get("title") or not headers.get("artist"):
        raise ValueError("needs title: and artist: lines")
    if not sections:
        raise ValueError("needs at least one section")
    if "bpm" in headers:
        try:
            bpm = float(headers["bpm"])
        except ValueError:
            bpm = 0
        if not 20 <= bpm <= 300:
            print(f"  note: bpm “{headers['bpm']}” is outside 20–300, so the app ignores it")
    ordered = sorted(sections)
    for (s1, e1), (s2, _) in zip(ordered, ordered[1:]):
        if s2 < e1:
            raise ValueError("sections overlap")
    return headers, sections


def main() -> int:
    errors = []

    def fail(message):
        errors.append(message)
        print(f"✗ {message}")

    try:
        index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
        songs = index["songs"]
        if not isinstance(songs, dict):
            raise ValueError
    except Exception:
        print("✗ index.json must be {\"songs\": {\"<key>\": \"songs/…/….wbmm\"}}")
        return 1

    indexed = set()
    for key, path in songs.items():
        if not (isinstance(path, str) and path.endswith(".wbmm") and not path.startswith("/")
                and ".." not in path and "://" not in path):
            fail(f"index.json: “{key}” points to “{path}”, which isn't a .wbmm path inside this repository")
            continue
        file = ROOT / path
        if not file.is_file():
            fail(f"index.json: “{key}” points to “{path}”, which doesn't exist")
            continue
        indexed.add(file.resolve())
        try:
            headers, _ = parse(file.read_text(encoding="utf-8"))
        except ValueError:
            continue  # Reported below with the file.
        expected = lookup_key(headers["artist"], headers["title"])
        isrc = headers.get("isrc", "").upper()
        if key != expected and key != isrc:
            fail(f"index.json: key “{key}” doesn't match {path}; use “{expected}”" + (f" or “{isrc}”" if isrc else ""))

    keys = list(songs.keys())
    if keys != sorted(keys):
        print("  note: keep index.json keys in alphabetical order")

    files = sorted(ROOT.glob("songs/**/*.wbmm")) + sorted(ROOT.glob("examples/*.wbmm"))
    for file in files:
        relative = file.relative_to(ROOT)
        if file.stat().st_size > MAX_BYTES:
            fail(f"{relative}: larger than 64 KB")
            continue
        try:
            parse(file.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            fail(f"{relative}: must be UTF-8 text")
            continue
        except ValueError as error:
            fail(f"{relative}: {error}")
            continue
        if relative.parts[0] == "songs" and file.resolve() not in indexed:
            fail(f"{relative}: not listed in index.json")

    if errors:
        print(f"\n{len(errors)} problem(s) found.")
        return 1
    print(f"✓ index.json and {len(files)} .wbmm file(s) look good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
