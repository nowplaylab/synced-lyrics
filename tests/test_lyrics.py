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

    def test_parse_lrc_time_formats(self):
        # [мм:сс:xx] через двоеточие, [мм:сс] без долей и тысячные доли — строки не теряются
        lines = synced_lyrics.parse_lrc('[00:10:50]Раз\n[00:11]Два\n[00:12.345]Три\n[00:13:05]<00:13:05>Четыре')
        self.assertEqual(lines, [{'t': 10500, 'text': 'Раз'}, {'t': 11000, 'text': 'Два'},
                                 {'t': 12345, 'text': 'Три'}, {'t': 13050, 'text': 'Четыре'}])
        self.assertEqual(synced_lyrics.parse_lrc('[length:3:34]\n[ti:Песня]'), [])   # метки шапки — не строки

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


class LocalFilesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import tempfile, os
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        os.makedirs(os.path.join(d, 'Кассета'))
        self.by_name = os.path.join(d, 'Кассета', 'Кассета - Ночной маршрут.lrc')
        with open(self.by_name, 'w', encoding='utf-8') as f:
            f.write('[length:3:34]\n[00:06.00]Мы едем по ночному маршруту\n[00:15.40]Пока горит этот свет\n')
        with open(os.path.join(d, 'track07.lrc'), 'w', encoding='cp1251') as f:   # имя ни о чём, зато метки
            f.write('[ti:Рассвет]\n[ar:Кассета]\n[offset:500]\n[00:10.00]<00:10.00>Рассвет <00:10.80>догонит\n')
        with open(os.path.join(d, 'Без времени.txt'), 'w', encoding='utf-8') as f:
            f.write('Просто текст\nбез таймингов\n')
        self.dirs = [d]

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_by_name_tags_and_txt(self):
        loc = synced_lyrics.local
        self.assertEqual(loc.find(self.dirs, 'Ночной маршрут', 'Кассета', 214000), self.by_name)
        self.assertEqual(loc.find(self.dirs, 'НОЧНОЙ  маршрут (Remastered)', 'кассета'), self.by_name)
        self.assertIsNone(loc.find(self.dirs, 'Ночной маршрут', 'Кассета', 260000))   # другая длина
        self.assertTrue(loc.find(self.dirs, 'Рассвет', 'Кассета').endswith('track07.lrc'))
        self.assertIsNone(loc.find(self.dirs, 'Рассвет', 'Другая группа'))
        self.assertTrue(loc.find(self.dirs, 'Без времени').endswith('.txt'))
        self.assertIsNone(loc.find(['/нет/такой/папки'], 'Ночной маршрут'))

    def test_read(self):
        l = synced_lyrics.local.read(synced_lyrics.local.find(self.dirs, 'Рассвет', 'Кассета'))
        self.assertEqual(l.source, 'file')
        self.assertEqual(l.synced, [{'t': 9500, 'text': 'Рассвет догонит'}])      # offset и время слов
        l = synced_lyrics.local.read(synced_lyrics.local.find(self.dirs, 'Без времени'))
        self.assertEqual((l.synced, l.plain), ([], 'Просто текст\nбез таймингов'))

    async def test_fetch_uses_files_first_without_network(self):
        async with aiohttp.ClientSession() as http:
            l = await synced_lyrics.fetch(http, 'Ночной маршрут', 'Кассета', duration_ms=214000,
                                          lrclib='http://127.0.0.1:9/api', use_yandex=False, local_dirs=self.dirs)
        self.assertEqual(l.source, 'file')
        self.assertEqual(l.synced[1], {'t': 15400, 'text': 'Пока горит этот свет'})


if __name__ == '__main__':
    unittest.main()
