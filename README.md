<p align="center"><a href="https://github.com/nowplaylab/synced-lyrics"><img src="https://raw.githubusercontent.com/nowplaylab/synced-lyrics/main/docs/banner.png" alt="synced-lyrics" width="100%"></a></p>

<p align="center"><b>English</b> &nbsp;·&nbsp; <a href="https://github.com/nowplaylab/synced-lyrics/blob/main/README.ru.md">Русский</a> &nbsp;·&nbsp; <a href="https://pypi.org/project/lrclib-synced/">PyPI</a></p>

<p align="center">
<a href="https://pypi.org/project/lrclib-synced/"><img src="https://img.shields.io/pypi/v/lrclib-synced?style=flat-square&labelColor=3B3C61&color=772556&label=PyPI" alt="PyPI"></a>
<a href="https://github.com/nowplaylab/synced-lyrics/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/nowplaylab/synced-lyrics/tests.yml?branch=main&style=flat-square&labelColor=3B3C61&label=tests" alt="tests"></a>
<img src="https://img.shields.io/badge/python-3.9+-55507F?style=flat-square&labelColor=3B3C61" alt="Python 3.9+">
<a href="https://github.com/nowplaylab/synced-lyrics/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-8B85A7?style=flat-square&labelColor=3B3C61" alt="MIT"></a>
</p>

Song lyrics with line and word timings for karaoke-style display. Supports your own files, the optional Spicy Lyrics API (with your key), [LRCLIB](https://lrclib.net), and Yandex Music as a plain-text fallback.

Timed lyrics are only accepted when the track length matches (within 4 s, or 2 s when the artist is unknown). Otherwise a remix or live version would show lines at the wrong moments; you get plain lyrics instead.

Made by [nowplaylab](https://github.com/nowplaylab) for [NowPlaying](https://github.com/nowplaylab/nowplaying-display).

## Install

```
pip install lrclib-synced
```

Python 3.9+, depends only on aiohttp. On PyPI the package is called **lrclib-synced** (`synced-lyrics` is too close to another project there); you still `import synced_lyrics`.

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

- `fetch()` never raises on network errors. Busy or failing services are retried a few times; if one still does not answer, you get `lyrics.complete == False`. Empty with `complete=True` means there really are no lyrics; empty with `complete=False` means "could not check, ask again later", so do not cache it for long.
- Titles with extras like `(feat. …)`, `(Prod. by …)` or ` - Remastered 2011` are searched again without them (`synced_lyrics.simplify_title()`).
- `use_yandex=False` turns the fallback off.
- `local_dirs=['~/Music/Lyrics']` checks your own files first, with no network: `Artist - Title.lrc`, `Title - Artist.lrc` or `Title.lrc` (a `.txt` works too, as plain lyrics). A `.lrc` with any name is found by its `[ti:]` and `[ar:]` tags. If the file has `[length:3:34]`, it is used only when the track length matches (within 4 s). `lyrics.source` is then `'file'`. Use `synced_lyrics.local.find()` and `read()` on their own if you like.
- `parse_lrc()` reads times written as `[mm:ss]`, `[mm:ss.xx]` or `[mm:ss:xx]`, understands `[offset:±ms]` and drops per-word times (`<00:10.80>`), keeping the line.
- `synced_lyrics.parse_lrc(text)` parses any LRC text on its own.
- `synced_lyrics.yandex` has the search helpers: `find_tracks()`, `same_track()`, `plain_lyrics()`.
- LRCLIB asks clients to send their own User-Agent.

## Licence

MIT. Not affiliated with LRCLIB or Yandex.

## Spicy Lyrics (0.4.0)

Pass `spicy_key=your_key` to `fetch()` to enable the official [Spicy Lyrics API](https://developers.spicylyrics.org/docs). Order: local files → Spicy → LRCLIB → Yandex. With no key, the existing behaviour is unchanged. Search uses title, artist and duration; only exact matches within 4 seconds are selected. You may pass `spicy_track_id` if you already know the Spotify, ISRC or Apple Music id.

```python
lyrics = await synced_lyrics.fetch(
    http, title, artist, duration_ms=duration_ms, spicy_key=your_key,
)
```

The key is an explicit argument belonging to the calling application. There is no default or shared application key in this package.

`lyrics.source == 'spicy'` identifies this API; `lyrics.attribution` names the actual provider (Apple Music, Spotify or Spicy Lyrics) and the community uploader/maker when present. Display these credits with the lyrics and link contributor profiles. Do not cache API lyrics longer than 30 days; NowPlaying uses memory only and expires them after 3 days.

Timed lines may additionally contain `end` and `words`: each word/syllable has `t`, `end` (absolute milliseconds), `start`, `stop` (UTF-16 offsets into the line text). `IsPartOfWord` syllables are joined without spaces. Lines with no word timings remain line-synced; no synthetic timings are generated. Static responses remain plain text.

Use your own key. Public native apps require client access with the explicit “no Origin” option; never ship a secret key. Requests have timeouts, errors fall back to the other providers, and rate limits impose a cooldown without immediate retries. This implementation uses the documented API, not the AGPL PulseSync add-on code.
