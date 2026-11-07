"""Открытый API Яндекс Музыки (без входа в аккаунт): поиск трека и обычный текст песни."""
import asyncio
import re

import aiohttp

YM_API = 'https://api.music.yandex.net'


def norm(s):
    s = (s or '').lower().replace('ё', 'е')
    s = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', s)   # (feat. …), [Explicit] и т. п.
    return re.sub(r'[^\w]+', ' ', s).strip()


def artist_set(artist):
    return {norm(a) for a in re.split(r',|&| feat\.? | ft\.? | x ', artist or '', flags=re.I) if a.strip()}


def same_track(title, artist, dur_ms, cand_title, cand_artists, cand_dur_ms, tolerance_ms=6000):
    """Тот же ли трек: название совпало, хотя бы один исполнитель общий, длительность рядом."""
    if norm(cand_title) != norm(title):
        return False
    want = artist_set(artist)
    have = set().union(*(artist_set(a) for a in cand_artists)) if cand_artists else set()
    if want and not (have & want):   # у разных сервисов дуэт бывает и одной строкой, и списком
        return False
    return not (dur_ms and cand_dur_ms and abs(cand_dur_ms - dur_ms) > tolerance_ms)


async def call(http, path, params=None, tries=3):
    """(ok, result). ok=False — Яндекс так и не ответил (сеть, перегрузка); ok=True и None — ответил, что нет."""
    for i in range(tries):  # Яндекс иногда отвечает пустотой на первый запрос
        try:
            async with http.get(f'{YM_API}/{path}', params=params) as r:
                if r.status == 404:
                    return True, None
                if r.status == 200:
                    try:
                        return True, ((await r.json(content_type=None)) or {}).get('result')
                    except ValueError:
                        pass
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            pass
        if i < tries - 1:
            await asyncio.sleep(1)
    return False, None


async def api(http, path, params=None):
    """result из ответа или None."""
    return (await call(http, path, params))[1]


def _matching(res, title, artist, dur_ms):
    tracks = ((res or {}).get('tracks') or {}).get('results') or []
    return [t for t in tracks if same_track(title, artist, dur_ms, t.get('title'),
                                            [a.get('name') for a in t.get('artists') or []], t.get('durationMs'))]


async def find_tracks(http, title, artist, dur_ms):
    """Треки из поиска Яндекс Музыки, которые совпали с играющим."""
    res = await api(http, 'search', {'text': f'{artist} {title}'.strip(), 'type': 'track', 'page': '0'})
    return _matching(res, title, artist, dur_ms)


async def plain_lyrics_checked(http, title, artist, dur_ms):
    """(текст или '', ok). ok=False — Яндекс не ответил, «текста нет» утверждать нельзя."""
    ok, res = await call(http, 'search', {'text': f'{artist} {title}'.strip(), 'type': 'track', 'page': '0'})
    if not ok:
        return '', False
    for t in _matching(res, title, artist, dur_ms)[:2]:
        ok2, sup = await call(http, f'tracks/{t["id"]}/supplement')
        ok = ok and ok2
        text = ((sup or {}).get('lyrics') or {}).get('fullLyrics') or ''
        if text.strip():
            return text, True
    return '', ok


async def plain_lyrics(http, title, artist, dur_ms):
    """Обычный текст песни (без таймингов) или ''."""
    return (await plain_lyrics_checked(http, title, artist, dur_ms))[0]
