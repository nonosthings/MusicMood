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
INTENSITIES = {"whisper", "soft", "normal", "strong", "intense", "shout"}
EFFECTS = {"glow", "shake", "pulse"}
FONTS = {"standard", "rounded", "serif", "monospaced", "mono", "avenir", "georgia", "futura", "courier", "handwriting"}


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


def lyric_seconds(text: str):
    parts = text.split(":")
    if len(parts) != 2 or not parts[0].isdigit():
        return None
    try:
        secs = float(parts[1])
    except ValueError:
        return None
    if not 0 <= secs < 60 or parts[1].startswith("-"):
        return None
    return int(parts[0]) * 60 + secs


def parse_wbel(text: str):
    """Mirrors ExpressiveLyricsFile.parse: styles only, never lyric text."""
    headers, styles = {}, []
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
                    raise ValueError(f"expected a style like [2:31.4-2:35 intense bold], found “{body}”")
                words = body[1:].split()
                if not words:
                    raise ValueError("empty style")
                bounds = words[0].split("-")
                start = lyric_seconds(bounds[0]) if len(bounds) == 2 else None
                end = lyric_seconds(bounds[1]) if len(bounds) == 2 else None
                if start is None or end is None or end <= start:
                    raise ValueError(f"“{words[0]}” isn't a time range like 2:31.4-2:35.1")
                seen = set()
                for word in (w.lower() for w in words[1:]):
                    kind = ("intensity" if word in INTENSITIES else "bold" if word == "bold" else "italic" if word == "italic"
                            else "effect" if word in EFFECTS else "color" if word.startswith("color=") and word[6:] in HINTS
                            else "font" if word in FONTS else None)
                    if kind is None or kind in seen:
                        raise ValueError(f"“{word}” isn't allowed in [{body[1:]}]")
                    seen.add(kind)
                styles.append((start, end))
            continue
        key = line.split(":", 1)[0].strip().lower() if ":" in line else None
        if key not in ("title", "artist", "isrc"):
            raise ValueError(f"only title:, artist: and isrc: lines are allowed (no lyric text): “{line[:40]}”")
        headers[key] = line.split(":", 1)[1].strip()
    if not headers.get("title") or not headers.get("artist"):
        raise ValueError("needs title: and artist: lines")
    if not styles:
        raise ValueError("needs at least one style")
    return headers, styles


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

    lyrics = index.get("lyrics", {})
    if not isinstance(lyrics, dict):
        fail("index.json: \"lyrics\" must map keys to lyrics/….wbel files")
        lyrics = {}
    for key, path in lyrics.items():
        if not (isinstance(path, str) and path.endswith(".wbel") and not path.startswith("/") and ".." not in path and "://" not in path):
            fail(f"index.json: lyrics “{key}” points to “{path}”, which isn't a .wbel path inside this repository")
            continue
        file = ROOT / path
        if not file.is_file():
            fail(f"index.json: lyrics “{key}” points to “{path}”, which doesn't exist")
            continue
        indexed.add(file.resolve())
        try:
            headers, _ = parse_wbel(file.read_text(encoding="utf-8"))
        except ValueError:
            continue
        expected = lookup_key(headers["artist"], headers["title"])
        isrc = headers.get("isrc", "").upper()
        if key != expected and key != isrc:
            fail(f"index.json: lyrics key “{key}” doesn't match {path}; use “{expected}”")

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

    wbel = sorted(ROOT.glob("lyrics/**/*.wbel")) + sorted(ROOT.glob("examples/*.wbel"))
    for file in wbel:
        relative = file.relative_to(ROOT)
        if file.stat().st_size > MAX_BYTES:
            fail(f"{relative}: larger than 64 KB")
            continue
        try:
            parse_wbel(file.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            fail(f"{relative}: {error}")
            continue
        if relative.parts[0] == "lyrics" and file.resolve() not in indexed:
            fail(f"{relative}: not listed in index.json's lyrics")
    files = files + wbel

    if errors:
        print(f"\n{len(errors)} problem(s) found.")
        return 1
    print(f"✓ index.json and {len(files)} .wbmm file(s) look good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
