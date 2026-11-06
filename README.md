# Music Mood

Community mood timings for **Music Mood** in [WidgetBlocks](https://github.com/nonosthings/WidgetBlocks). When a song's mood changes, the Music block's album-art background changes to a matching color from that song's cover. This repository holds the timings: when each part of a song starts and what it feels like.

The app downloads `index.json`, finds the song that's playing, then downloads that song's `.wbmm` file. Colors always come from the song's own cover art. If a cover has no color for a mood, the background keeps the color it already shows. If the app is offline or anything fails, it falls back to its usual album colors.

## Add a song

1. Make a `.wbmm` file in `songs/<artist>/<title>.wbmm`, using lowercase words joined by hyphens, like `songs/example-artist/example-song.wbmm`. Copy [`examples/example.wbmm`](examples/example.wbmm) to start.
2. Add the song to `index.json` (see [The index](#the-index)).
3. Open a pull request. A check runs the same rules the app uses and tells you what to fix.

Time the sections against the album version of the song, and listen through the whole song before submitting.

## The `.wbmm` format

```
# Lines starting with # are comments.
title: Example Song
artist: Example Artist
isrc: (optional) the recording's ISRC
bpm: (optional) beats per minute, 20–300

[calm 0:00-1:30]
[hype 1:31-3:10 lightest]
[intense 3:11-4:05 darkest]
```

- **Headers:** `title` and `artist` are required. `isrc` and `bpm` are optional.
- **Sections:** one `[mood start-end hint]` per section. Several sections can share a line: `[neutral 0:00-1:30] [anger 1:31-2:00]`.
- **Times:** `m:ss` or `h:mm:ss`. Each section must end after it starts. Gaps between sections keep the song's usual album colors.
- **Moods:** `neutral`, `calm`, `happy`, `sad`, `hype`, `anger`, `intense`.
- **Hints (optional):** pick which cover color a section uses instead of the mood's usual pick.
  - `dominant`: the color that covers the most of the cover.
  - `lightest`, `darkest`: the brightest or darkest cover color.
  - `vivid`: the most saturated cover color.

Anything else, like an unknown mood or hint, makes the whole file invalid, and the app ignores it.

### How moods pick colors

| Mood | Cover color it looks for | Second color |
| --- | --- | --- |
| neutral | the main color | slightly lighter |
| calm | blues, teals, greens, or a soft light color | slightly lighter |
| happy | yellows | lighter |
| sad | blues and purples | darker |
| hype | the most vivid color | the lightest color |
| anger | reds | the darkest color |
| intense | reds or purples, otherwise the main color | the darkest color |

A cover that is almost entirely one color uses that color for every mood.

## The index

`index.json` maps each song to its file:

```json
{
  "songs": {
    "exampleartist|examplesong": "songs/example-artist/example-song.wbmm"
  }
}
```

The key is the artist and title, lowercased, with only letters and numbers kept and anything in brackets removed, joined by `|`. For example, "Example Artist" and "Example Song (Remastered)" give `exampleartist|examplesong`. If the file has an `isrc`, you can also add the ISRC (uppercase) as a second key pointing to the same file. The check tells you the expected key if yours doesn't match.

Keep keys in alphabetical order to make reviews easier.

## Check your changes locally

```bash
python3 scripts/validate.py
```

## Expressive Lyrics (`.wbel`)

Expressive Lyrics change how lyric lines look in the WidgetBlocks player at moments in a song: bigger and bolder when it hits hard, softer and italic when it's quiet. The app shows the lyrics from LRCLIB and applies your styles to whichever line is on screen at that time.

**Never put lyric text in these files.** Lyrics are copyrighted. Files with any line other than `title:`, `artist:`, `isrc:` or a style are rejected.

```
title: Example Song
artist: Example Artist

[0:42.5-0:46 strong bold]
[1:10-1:18 whisper italic serif]
[2:31.4-2:35.1 shout bold glow color=vivid]
```

Each style is `[start-end words]`, with times as `m:ss` or `m:ss.s`. The words can include at most one of each:

- **Intensity:** `whisper`, `soft`, `normal`, `strong`, `intense`, `shout`.
- **Weight and slant:** `bold`, `italic`.
- **Font:** `rounded`, `serif`, `mono`, `avenir`, `georgia`, `futura`, `courier`, `handwriting`.
- **Color:** `color=` with a cover-color hint (`dominant`, `lightest`, `darkest`, `vivid`).
- **Effect:** `glow`, `shake`, `pulse`. Effects are turned off for people using Reduce Motion.

Put the file in `lyrics/<artist>/<title>.wbel` and list it under `"lyrics"` in `index.json`, using the same key as the song:

```json
{
  "songs": { … },
  "lyrics": {
    "exampleartist|examplesong": "lyrics/example-artist/example-song.wbel"
  }
}
```

## What not to include

Only timings, moods and the song's title, artist, ISRC and tempo. No lyrics, audio, artwork or links.
