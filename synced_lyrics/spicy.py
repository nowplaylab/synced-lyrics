"""Spicy Lyrics API v1. Независимый клиент по официальной документации.

Ключ передаёт приложение; чужие ключи и код PulseSync здесь не используются.
Тайминги в результате — миллисекунды, диапазоны символов — UTF-16 для Android.
"""
import asyncio
import math
import re
import time
from urllib.parse import quote

import aiohttp

API = 'https://api.spicylyrics.org/v1'
_cooldown = {}
PROVIDERS = {'spicy_lyrics': 'Spicy Lyrics', 'apple_music': 'Apple Music',
             'spotify': 'Spotify', 'unknown': 'Spicy Lyrics'}


def _ms(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('invalid timestamp')
    return round(value * 1000)


def _length(text):
    return len(text.encode('utf-16-le')) // 2


def parse(payload):
    """Официальный LyricsEnvelope → Lyrics; неизвестный формат не считается отсутствием текста."""
    from . import Lyrics
    body = payload['Body']
    kind = body['Type']
    source = body.get('source', 'unknown')
    if source not in PROVIDERS:
        raise ValueError('unknown provider')
    credit = {'provider': PROVIDERS[source], 'url': 'https://spicylyrics.org'}
    if source == 'spicy_lyrics':
        attrs = body.get('UploadAttribution', {})
        for field, name in [('Uploader', 'uploader'), ('Maker', 'maker')]:
            person = attrs.get(field)
            if person:
                url = person.get('url', '')
                if not url.startswith('https://spicylyrics.org/'):
                    raise ValueError('invalid contributor link')
                credit[name] = {'name': person['username'], 'url': url}
        if 'uploader' not in credit:
            raise ValueError('community sync without uploader')
    lines = []
    if kind == 'Static':
        plain = '\n'.join(line['Text'] for line in body['Lines'])
    elif kind in ('Line', 'Syllable'):
        for line in body['Content']:
            if line.get('Type') != 'Vocal':
                continue
            group = line['Lead'] if kind == 'Syllable' else line
            start, end = _ms(group['StartTime']), _ms(group['EndTime'])
            if end < start:
                raise ValueError('reversed line')
            if kind == 'Line':
                item = {'t': start, 'end': end, 'text': line['Text']}
            else:
                text, words = '', []
                previous_start = start
                for syllable in group['Syllables']:
                    token = syllable['Text']
                    a, b = _ms(syllable['StartTime']), _ms(syllable['EndTime'])
                    if a < previous_start or b < a or a < start or b > end:
                        raise ValueError('invalid syllable interval')
                    previous_start = a
                    at = _length(text)
                    text += token
                    words.append({'t': a, 'end': b, 'start': at, 'stop': _length(text)})
                    if not syllable.get('IsPartOfWord', False):
                        text += ' '
                item = {'t': start, 'end': end, 'text': text.rstrip(), 'words': words}
            lines.append(item)
        lines.sort(key=lambda line: line['t'])
        plain = '\n'.join(line['text'] for line in lines)
    else:
        raise ValueError('unknown lyrics type')
    return Lyrics(lines, plain, 'spicy', attribution=credit)


def _norm(text):
    return re.sub(r'[\W_]+', ' ', text.casefold()).strip()


async def fetch(http, title, artist='', album='', duration_ms=0, *, key='', track_id='', base=API):
    """Без ключа отключён. При отказе/лимите не повторяет запросы к этому ключу сразу.

    Автовыбор — только точное совпадение названия/исполнителя и длительности ±4 с.
    track_id — Spotify ID, ISRC или Apple Music ID, если приложение уже знает его.
    """
    from . import Lyrics
    if not key:
        return Lyrics()
    if _cooldown.get((base, key), 0) > time.monotonic():
        return Lyrics(complete=False)

    async def request(path, params=None):
        async with http.get(base + path, params=params,
                            headers={'Authorization': 'Bearer ' + key},
                            timeout=aiohttp.ClientTimeout(total=7)) as response:
            if response.status == 404:
                return None
            if response.status != 200:
                if response.status in (401, 403, 429, 503):
                    try:
                        delay = max(60, min(3600, int(response.headers.get('Retry-After', '300'))))
                    except ValueError:
                        delay = 300
                    if len(_cooldown) > 100:
                        _cooldown.clear()
                    _cooldown[(base, key)] = time.monotonic() + delay
                raise ValueError('Spicy API unavailable')
            return await response.json(content_type=None)

    try:
        if not track_id:
            # Неизвестные необязательные поля пропускаем: API не принимает пустые строки.
            params = {k: v for k, v in {'title': title, 'artist': artist, 'album': album}.items() if v}
            if duration_ms:
                params['duration'] = duration_ms / 1000
            result = await request('/tracks/search', params)
            candidates = (result or {}).get('Body', {}).get('results', [])
            for candidate in candidates:
                if candidate.get('tier') != 'exact' or _norm(candidate.get('title', '')) != _norm(title):
                    continue
                artists = candidate.get('artists', [])
                # Плеер присылает участников одной строкой («A, B»), API — списком.
                # Сравниваем и отдельное имя, и весь состав, не ослабляя tier/длительность.
                names = [_norm(a) for a in artists]
                names.append(_norm(' '.join(artists)))
                if not artist or _norm(artist) not in names:
                    continue
                if duration_ms and abs(_ms(candidate.get('duration', 0)) - duration_ms) > 4000:
                    continue
                track_id = candidate['id']
                break
        if not track_id:
            return Lyrics()
        payload = await request('/lyrics/' + quote(track_id, safe=''))
        return parse(payload) if payload else Lyrics()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError, KeyError,
            AttributeError, IndexError, OverflowError, OSError):
        return Lyrics(complete=False)
