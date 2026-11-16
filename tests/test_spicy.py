import unittest

import aiohttp
from aiohttp import web

import synced_lyrics
from synced_lyrics import spicy


def envelope(source='apple_music'):
    return {'Body': {'Type': 'Syllable', 'source': source, 'Content': [
        {'Type': 'Vocal', 'Lead': {'StartTime': 1, 'EndTime': 4, 'Syllables': [
            {'Text': 'Ноч', 'StartTime': 1, 'EndTime': 2, 'IsPartOfWord': True},
            {'Text': 'ной', 'StartTime': 2, 'EndTime': 3},
            {'Text': 'маршрут', 'StartTime': 3, 'EndTime': 4}]}}]}}


class ParseTest(unittest.TestCase):
    def test_syllables_preserve_word_boundaries(self):
        got = spicy.parse(envelope())
        self.assertEqual(got.synced[0], {'t': 1000, 'end': 4000, 'text': 'Ночной маршрут', 'words': [
            {'t': 1000, 'end': 2000, 'start': 0, 'stop': 3},
            {'t': 2000, 'end': 3000, 'start': 3, 'stop': 6},
            {'t': 3000, 'end': 4000, 'start': 7, 'stop': 14}]})
        self.assertEqual(got.attribution['provider'], 'Apple Music')
        self.assertNotIn('uploader', got.attribution)

    def test_utf16_ranges(self):
        data = envelope()
        data['Body']['Content'][0]['Lead']['Syllables'][0]['Text'] = '🌙'
        got = spicy.parse(data)
        self.assertEqual(got.synced[0]['words'][0]['stop'], 2)
        self.assertEqual(got.synced[0]['words'][1]['start'], 2)

    def test_conditional_credits(self):
        data = envelope('spicy_lyrics')
        with self.assertRaises(ValueError):
            spicy.parse(data)
        data['Body']['UploadAttribution'] = {'Uploader': {
            'username': 'Автор', 'url': 'https://spicylyrics.org/uid/123'}}
        self.assertEqual(spicy.parse(data).attribution['uploader']['name'], 'Автор')
        self.assertNotIn('maker', spicy.parse(data).attribution)

    def test_invalid_timing(self):
        data = envelope()
        data['Body']['Content'][0]['Lead']['Syllables'][0]['EndTime'] = float('nan')
        with self.assertRaises(ValueError):
            spicy.parse(data)

    def test_line_and_static(self):
        data = {'Body': {'Type': 'Line', 'source': 'spotify', 'Content': [
            {'Type': 'Vocal', 'Text': 'Песня', 'StartTime': 1, 'EndTime': 2}]}}
        self.assertEqual(spicy.parse(data).synced[0]['t'], 1000)
        data['Body'] = {'Type': 'Static', 'source': 'spotify', 'Lines': [{'Text': 'Песня'}]}
        self.assertEqual(spicy.parse(data).plain, 'Песня')


class ApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        spicy._cooldown.clear()
        self.calls = []
        self.status = 200
        self.tier = 'exact'
        self.duration = 20
        self.artists = ['Кассета']
        async def handler(request):
            self.calls.append((request.path, request.headers.get('Authorization')))
            if self.status != 200:
                return web.json_response({}, status=self.status, headers={'Retry-After': '300'})
            if request.path.endswith('search'):
                if any(not value for value in request.query.values()):
                    return web.json_response({'Body': {'error': 'invalid_request'}}, status=400)
                return web.json_response({'Body': {'results': [{'id': 'abc', 'title': 'Ночной маршрут',
                    'artists': self.artists, 'duration': self.duration, 'tier': self.tier}]}})
            if request.path.startswith('/lyrics/'):
                return web.json_response(envelope())
            return web.json_response([], status=200)
        app = web.Application()
        app.router.add_get('/{rest:.*}', handler)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        self.base = 'http://127.0.0.1:' + str(site._server.sockets[0].getsockname()[1])
        self.http = aiohttp.ClientSession()

    async def asyncTearDown(self):
        await self.http.close()
        await self.runner.cleanup()

    async def fetch(self):
        return await spicy.fetch(self.http, 'Ночной маршрут', 'Кассета', duration_ms=20000,
                                 key='test', base=self.base)

    async def test_search_then_fetch(self):
        got = await self.fetch()
        self.assertEqual(got.source, 'spicy')
        self.assertEqual(self.calls, [('/tracks/search', 'Bearer test'), ('/lyrics/abc', 'Bearer test')])

    async def test_wrong_version_not_selected(self):
        self.tier = 'version'
        self.assertFalse(await self.fetch())
        self.assertEqual(len(self.calls), 1)
        self.tier, self.duration = 'exact', 100
        self.assertFalse(await self.fetch())
        self.assertEqual(len(self.calls), 2)

    async def test_multiple_artists_from_player_match_catalog_list(self):
        self.artists = ['Кассета', 'Гость']
        got = await spicy.fetch(self.http, 'Ночной маршрут', 'Кассета, Гость', duration_ms=20000,
                                key='test', base=self.base)
        self.assertEqual(got.source, 'spicy')
        self.assertEqual(len(self.calls), 2)

    async def test_different_collaboration_not_selected(self):
        self.artists = ['Кассета', 'Другой']
        got = await spicy.fetch(self.http, 'Ночной маршрут', 'Кассета, Гость', duration_ms=20000,
                                key='test', base=self.base)
        self.assertFalse(got)
        self.assertEqual(len(self.calls), 1)

    async def test_rate_limit_waits_without_retry(self):
        self.status = 429
        self.assertFalse((await self.fetch()).complete)
        self.assertFalse((await self.fetch()).complete)
        self.assertEqual(len(self.calls), 1)

    async def test_missing_key_makes_no_calls(self):
        self.assertFalse(await spicy.fetch(self.http, 'Track', base=self.base))
        self.assertEqual(self.calls, [])

    async def test_fallback_and_completion(self):
        self.status = 404
        got = await synced_lyrics.fetch(self.http, 'Ночной маршрут', 'Кассета',  duration_ms=20000,
            spicy_key='test', spicy_base=self.base, lrclib=self.base, use_yandex=False)
        self.assertTrue(got.complete)
        self.assertFalse(got)

    async def test_spicy_precedes_lrclib(self):
        got = await synced_lyrics.fetch(self.http, 'Ночной маршрут', 'Кассета', duration_ms=20000,
            spicy_key='test', spicy_base=self.base, lrclib=self.base, use_yandex=False)
        self.assertEqual(got.source, 'spicy')
        self.assertEqual(len(self.calls), 2)
