import unittest

import aiohttp
from aiohttp import web

import synced_lyrics
from synced_lyrics import yandex

LRC = '[00:10.50]Первая строка\n[00:12.00][01:00.00]Припев\n[ar:Кто-то]\n'


def make_app():
    hits = {}

    async def lrc_get(r):
        if r.query.get('track_name') == 'Песня' and r.query.get('duration') == '200':
            return web.json_response({'duration': 201, 'syncedLyrics': LRC, 'plainLyrics': 'Первая строка\nПрипев'})
        return web.json_response({}, status=404)

    async def lrc_search(r):
        name = r.query.get('track_name')
        if name == 'Капризная':                       # первый раз сервис перегружен, потом отвечает
            hits[name] = hits.get(name, 0) + 1
            if hits[name] == 1:
                return web.json_response({}, status=503)
            return web.json_response([{'duration': 200, 'syncedLyrics': LRC, 'plainLyrics': 'x'}])
        if name == 'Лежит':
            return web.json_response({}, status=503)
        if name == 'Песня два':
            return web.json_response([{'duration': 200, 'syncedLyrics': LRC, 'plainLyrics': 'x'}])
        if name == 'Ремикс':
            return web.json_response([{'duration': 260, 'syncedLyrics': LRC, 'plainLyrics': 'только текст'}])
        return web.json_response([])

    async def ym_search(r):
        if 'Лежит' in r.query.get('text', ''):
            return web.json_response({}, status=503)
        return web.json_response({'result': {'tracks': {'results': [
            {'id': 7, 'title': 'Редкая', 'artists': [{'name': 'Группа'}], 'durationMs': 180000}]}}})

    async def ym_supplement(r):
        return web.json_response({'result': {'lyrics': {'fullLyrics': 'Текст из Яндекса'}}})

    app = web.Application()
    app.add_routes([web.get('/api/get', lrc_get), web.get('/api/search', lrc_search),
                    web.get('/search', ym_search), web.get('/tracks/7/supplement', ym_supplement)])
    return app


class LyricsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runner = web.AppRunner(make_app())
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        self.base = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        yandex.YM_API = self.base
        self.http = aiohttp.ClientSession()

    async def asyncTearDown(self):
        await self.http.close()
        await self.runner.cleanup()

    def test_parse_lrc(self):
        lines = synced_lyrics.parse_lrc(LRC)
        self.assertEqual(lines, [{'t': 10500, 'text': 'Первая строка'}, {'t': 12000, 'text': 'Припев'},
                                 {'t': 60000, 'text': 'Припев'}])

    async def test_synced(self):
        l = await synced_lyrics.fetch(self.http, 'Песня', 'Исполнитель', duration_ms=200000, lrclib=self.base + '/api')
        self.assertEqual((l.source, len(l.synced), l.synced[0]['text']), ('lrclib', 3, 'Первая строка'))

    async def test_wrong_duration_gives_plain_only(self):
        l = await synced_lyrics.fetch(self.http, 'Ремикс', 'Исполнитель', duration_ms=200000, lrclib=self.base + '/api')
        self.assertEqual((l.synced, l.plain, l.source), ([], 'только текст', 'lrclib'))

    async def test_yandex_fallback(self):
        l = await synced_lyrics.fetch(self.http, 'Редкая', 'Группа', duration_ms=181000, lrclib=self.base + '/api')
        self.assertEqual((l.plain, l.source), ('Текст из Яндекса', 'yandex'))
        nothing = await synced_lyrics.fetch(self.http, 'Редкая', 'Группа', duration_ms=181000,
                                            lrclib=self.base + '/api', use_yandex=False)
        self.assertFalse(nothing)

    async def test_retry_after_overload(self):
        l = await synced_lyrics.fetch(self.http, 'Капризная', 'Исполнитель', duration_ms=200000, lrclib=self.base + '/api')
        self.assertEqual((l.source, len(l.synced), l.complete), ('lrclib', 3, True))

    async def test_down_is_not_nothing(self):
        l = await synced_lyrics.fetch(self.http, 'Лежит', 'Исполнитель', duration_ms=200000, lrclib=self.base + '/api')
        self.assertFalse(l)
        self.assertFalse(l.complete)                   # не «текста нет», а «не смогли проверить»
        l = await synced_lyrics.fetch(self.http, 'Ничего', 'Исполнитель', duration_ms=200000, lrclib=self.base + '/api',
                                      use_yandex=False)
        self.assertEqual((bool(l), l.complete), (False, True))

    async def test_title_with_extras(self):
        l = await synced_lyrics.fetch(self.http, 'Песня два (Prod. by Кто-то)', 'Исполнитель', duration_ms=200000,
                                      lrclib=self.base + '/api', use_yandex=False)
        self.assertEqual(len(l.synced), 3)
        self.assertEqual(synced_lyrics.simplify_title('Song - Remastered 2011'), 'Song')
        self.assertEqual(synced_lyrics.simplify_title('В миноре (Prod. by Wex & Lawzy)'), 'В миноре')
        self.assertEqual(synced_lyrics.simplify_title('Mix - Tape'), 'Mix - Tape')

    def test_same_track(self):
        self.assertTrue(yandex.same_track('Song (feat. X)', 'A & B', 200000, 'Song', ['B'], 203000))
        self.assertFalse(yandex.same_track('Song', 'A', 200000, 'Song', ['C'], 200000))
        self.assertFalse(yandex.same_track('Song', 'A', 200000, 'Song', ['A'], 220000))


if __name__ == '__main__':
    unittest.main()
