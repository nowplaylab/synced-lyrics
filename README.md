# synced-lyrics

**English** | [Русский](README.ru.md)

Song lyrics with a time for every line, for karaoke-style display. Looks on [LRCLIB](https://lrclib.net) first; if nothing is there, takes plain lyrics from Yandex Music (no account needed).

Timed lyrics are only accepted when the track length matches (within 4 s, or 2 s when the artist is unknown). Otherwise a remix or live version would show lines at the wrong moments; you get plain lyrics instead.

Made by [nowplaylab](https://github.com/nowplaylab) for [NowPlaying](https://github.com/nowplaylab/nowplaying-display).

## Install

```
pip install git+https://github.com/nowplaylab/synced-lyrics@v0.1.0
```

Python 3.9+, depends only on aiohttp.

## Use

```python
import aiohttp, synced_lyrics

async def main():
    async with aiohttp.ClientSession(headers={'User-Agent': 'my-app/1.0'}) as http:
        lyrics = await synced_lyrics.fetch(http, 'Blinding Lights', 'The Weeknd', duration_ms=200040)
        for line in lyrics.synced:          # [{'t': milliseconds, 'text': line}], empty if no timing
            print(line['t'], line['text'])
        print(lyrics.plain)                 # plain text, may exist without timing
        print(lyrics.source)                # 'lrclib', 'yandex' or ''
```

- `fetch()` never raises on network errors; it logs them and returns empty `Lyrics` (falsy).
- `use_yandex=False` turns the fallback off.
- `synced_lyrics.parse_lrc(text)` parses any LRC text on its own.
- `synced_lyrics.yandex` has the search helpers: `find_tracks()`, `same_track()`, `plain_lyrics()`.
- LRCLIB asks clients to send their own User-Agent.

## Licence

MIT. Not affiliated with LRCLIB or Yandex.
