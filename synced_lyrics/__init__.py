"""Тексты песен со временем строк: LRCLIB (синхронный и обычный текст) и запасной — Яндекс Музыка.

    lyrics = await synced_lyrics.fetch(http, 'Blinding Lights', 'The Weeknd', duration_ms=200040)
    for line in lyrics.synced:      # [{'t': мс, 'text': строка}] — пусто, если таймингов нет
        ...
    lyrics.plain                    # обычный текст (может быть и без синхронного)
    lyrics.source                   # 'lrclib', 'yandex' или ''

Синхронный текст берётся, только если длительность совпала (±4 с; без исполнителя — ±2 с),
иначе строки разъедутся с песней (ремикс, live, другая версия).
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field

import aiohttp

from . import yandex

__version__ = '0.1.1'
__all__ = ['Lyrics', 'fetch', 'parse_lrc', 'LRCLIB']

log = logging.getLogger('synced_lyrics')
LRCLIB = 'https://lrclib.net/api'


@dataclass
class Lyrics:
    synced: list = field(default_factory=list)   # [{'t': мс, 'text': строка}]
    plain: str = ''
    source: str = ''

    def __bool__(self):
        return bool(self.synced or self.plain)


def parse_lrc(text):
    """LRC → [{'t': мс, 'text': строка}] по времени. Строка с несколькими метками повторяется."""
    lines = []
    for raw in (text or '').splitlines():
        stamps = re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', raw)
        words = re.sub(r'\[[^\]]*\]', '', raw).strip()
        for m, s in stamps:
            lines.append({'t': int((int(m) * 60 + float(s)) * 1000), 'text': words})
    return sorted(lines, key=lambda l: l['t'])


async def from_lrclib(http, title, artist='', album='', duration_ms=0, base=LRCLIB):
    q = {'track_name': title, 'artist_name': artist}
    cands = []
    if artist:
        params = dict(q, album_name=album, duration=int(duration_ms / 1000)) if duration_ms else dict(q)
        async with http.get(f'{base}/get', params=params) as r:
            if r.status == 200:
                cands.append(await r.json(content_type=None))
    async with http.get(f'{base}/search', params=q if artist else {'q': title}) as r:
        if r.status == 200:
            cands += await r.json(content_type=None)

    def diff(c):
        return abs((c.get('duration') or 0) * 1000 - duration_ms) if duration_ms and c.get('duration') else None

    limit = 4000 if artist else 2000    # без исполнителя — строже
    synced = [c for c in cands if c.get('syncedLyrics') and
              (diff(c) is None and duration_ms == 0 and artist or diff(c) is not None and diff(c) <= limit)]
    synced.sort(key=lambda c: diff(c) or 0)
    plain = [c for c in cands if c.get('plainLyrics') and (artist or (diff(c) is not None and diff(c) <= 5000))]
    plain.sort(key=lambda c: diff(c) if diff(c) is not None else 10 ** 9)
    if synced:
        return Lyrics(parse_lrc(synced[0]['syncedLyrics']), synced[0].get('plainLyrics') or '', 'lrclib')
    if plain:
        return Lyrics([], plain[0]['plainLyrics'], 'lrclib')
    return Lyrics()


async def fetch(http, title, artist='', album='', duration_ms=0, use_yandex=True, lrclib=LRCLIB):
    """Найти текст. http — aiohttp.ClientSession (лучше со своим User-Agent). Ошибки сети не бросает."""
    result = Lyrics()
    try:
        result = await from_lrclib(http, title, artist, album, duration_ms, lrclib)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError) as e:
        log.warning('lrclib: %s', e)
    if not result and use_yandex:
        try:
            text = await yandex.plain_lyrics(http, title, artist, duration_ms)
            if text:
                result = Lyrics([], text, 'yandex')
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError) as e:
            log.warning('yandex lyrics: %s', e)
    return result
