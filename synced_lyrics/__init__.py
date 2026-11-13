"""Тексты песен со временем строк: LRCLIB (синхронный и обычный текст) и запасной — Яндекс Музыка.

    lyrics = await synced_lyrics.fetch(http, 'Blinding Lights', 'The Weeknd', duration_ms=200040)
    for line in lyrics.synced:      # [{'t': мс, 'text': строка}] — пусто, если таймингов нет
        ...
    lyrics.plain                    # обычный текст (может быть и без синхронного)
    lyrics.source                   # 'file', 'lrclib', 'yandex' или ''
    lyrics.complete                 # False — какой-то источник не ответил, стоит спросить позже

Свои файлы: fetch(..., local_dirs=['~/Music/Lyrics']) сначала ищет «Исполнитель - Название.lrc»
(или .txt) в этих папках, см. synced_lyrics.local.

Синхронный текст берётся, только если длительность совпала (±4 с; без исполнителя — ±2 с),
иначе строки разъедутся с песней (ремикс, live, другая версия).

Пустой результат с complete=True значит «текста правда нет»; с complete=False — «не смогли
проверить» (сеть, сервис перегружен). Такой результат не стоит запоминать надолго.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field

import aiohttp

from . import yandex

__version__ = '0.3.1'
__all__ = ['Lyrics', 'fetch', 'parse_lrc', 'simplify_title', 'local', 'LRCLIB']

log = logging.getLogger('synced_lyrics')
LRCLIB = 'https://lrclib.net/api'
NET_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError, ValueError, OSError)


@dataclass
class Lyrics:
    synced: list = field(default_factory=list)   # [{'t': мс, 'text': строка}]
    plain: str = ''
    source: str = ''
    complete: bool = True                        # все источники ответили

    def __bool__(self):
        return bool(self.synced or self.plain)


_STAMP = r'(\d+):(\d+)(?:[.:](\d+))?'   # мм:сс, мм:сс.xx и мм:сс:xx (так пишут некоторые программы)


def _stamp_ms(mm, ss, frac):
    return (int(mm) * 60 + int(ss)) * 1000 + (round(float('0.' + frac) * 1000) if frac else 0)


def parse_lrc(text):
    """LRC → [{'t': мс, 'text': строка}] по времени. Строка с несколькими метками повторяется.
    Время в метке — [мм:сс], [мм:сс.xx] или [мм:сс:xx].
    Метка [offset:±мс] сдвигает все строки (плюс — раньше, как в стандарте LRC).
    Время отдельных слов <мм:сс.xx> внутри строки отбрасывается — остаётся текст строки."""
    m = re.search(r'^\s*\[offset:\s*([+-]?\d+)\s*\]', text or '', re.M | re.I)
    offset = int(m.group(1)) if m else 0
    lines = []
    for raw in (text or '').splitlines():
        stamps = re.findall(r'\[' + _STAMP + r'\]', raw)
        words = re.sub(r'<' + _STAMP + '>', '', re.sub(r'\[[^\]]*\]', '', raw))
        words = re.sub(r'\s+', ' ', words).strip()
        for mm, ss, frac in stamps:
            lines.append({'t': max(0, _stamp_ms(mm, ss, frac) - offset), 'text': words})
    return sorted(lines, key=lambda l: l['t'])


def simplify_title(title):
    """Название без приписок: (feat. …), (Prod. by …), [Explicit], « - Remastered 2011» и т. п."""
    t = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', title or '')
    t = re.sub(r'\s+[-–—]\s+[^-–—]*\b(remaster\w*|live|version|edit|mix|mono|stereo)\b.*$', '', t, flags=re.I)
    return t.strip() or (title or '').strip()


async def _get_json(http, url, params, tries=3):
    """(ok, данные). 200 — данные; 400/404 — (True, None): ответили, что нет; прочее — повтор."""
    for i in range(tries):
        try:
            async with http.get(url, params=params) as r:
                if r.status == 200:
                    return True, await r.json(content_type=None)
                if r.status in (400, 404):
                    return True, None
                log.info('%s -> %s', url, r.status)
        except NET_ERRORS as e:
            log.info('%s: %s', url, e)
        if i < tries - 1:
            await asyncio.sleep(0.6 * (i + 1) ** 2)
    return False, None


def _pick(cands, artist, duration_ms):
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


async def from_lrclib(http, title, artist='', album='', duration_ms=0, base=LRCLIB):
    """Lyrics из LRCLIB; complete=False, если LRCLIB не ответил."""
    complete = True
    short = simplify_title(title)
    best = Lyrics()
    for t in [title] + ([short] if short != title else []):
        q = {'track_name': t, 'artist_name': artist}
        cands = []
        if artist and duration_ms:   # /get без длительности LRCLIB не принимает
            ok, d = await _get_json(http, f'{base}/get', dict(q, album_name=album, duration=round(duration_ms / 1000)))
            complete &= ok
            if isinstance(d, dict):
                cands.append(d)
        ok, d = await _get_json(http, f'{base}/search', q if artist else {'q': t})
        complete &= ok
        if isinstance(d, list):
            cands += d
        got = _pick(cands, artist, duration_ms)
        if got.synced:
            return got
        if got and not best:
            best = got
    best.complete = complete
    return best


async def fetch(http, title, artist='', album='', duration_ms=0, use_yandex=True, lrclib=LRCLIB, local_dirs=None):
    """Найти текст. http — aiohttp.ClientSession (лучше со своим User-Agent). Ошибки сети не бросает:
    если источник не ответил даже после повторов, у результата complete=False.
    local_dirs — папки со своими .lrc/.txt: проверяются первыми, без сети (source='file')."""
    if local_dirs:
        try:
            path = await asyncio.get_running_loop().run_in_executor(
                None, local.find, local_dirs, title, artist, duration_ms)
            if path:
                got = local.read(path)
                if got:
                    return got
        except OSError as e:
            log.warning('local lyrics: %s', e)
    try:
        result = await from_lrclib(http, title, artist, album, duration_ms, lrclib)
    except NET_ERRORS as e:
        log.warning('lrclib: %s', e)
        result = Lyrics(complete=False)
    if not result and use_yandex:
        try:
            text, ok = await yandex.plain_lyrics_checked(http, title, artist, duration_ms)
        except NET_ERRORS as e:
            log.warning('yandex lyrics: %s', e)
            text, ok = '', False
        if text:
            return Lyrics([], text, 'yandex')
        result.complete = result.complete and ok
    return result


from . import local  # noqa: E402  (local использует Lyrics и parse_lrc отсюда)
