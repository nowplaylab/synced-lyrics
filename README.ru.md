<p align="center"><a href="https://github.com/nowplaylab/synced-lyrics"><img src="https://raw.githubusercontent.com/nowplaylab/synced-lyrics/main/docs/banner.png" alt="synced-lyrics" width="100%"></a></p>

<p align="center"><a href="https://github.com/nowplaylab/synced-lyrics/blob/main/README.md">English</a> &nbsp;·&nbsp; <b>Русский</b> &nbsp;·&nbsp; <a href="https://pypi.org/project/lrclib-synced/">PyPI</a></p>

<p align="center">
<a href="https://pypi.org/project/lrclib-synced/"><img src="https://img.shields.io/pypi/v/lrclib-synced?style=flat-square&labelColor=3B3C61&color=772556&label=PyPI" alt="PyPI"></a>
<a href="https://github.com/nowplaylab/synced-lyrics/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/nowplaylab/synced-lyrics/tests.yml?branch=main&style=flat-square&labelColor=3B3C61&label=%D1%82%D0%B5%D1%81%D1%82%D1%8B" alt="tests"></a>
<img src="https://img.shields.io/badge/python-3.9+-55507F?style=flat-square&labelColor=3B3C61" alt="Python 3.9+">
<a href="https://github.com/nowplaylab/synced-lyrics/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-8B85A7?style=flat-square&labelColor=3B3C61" alt="MIT"></a>
</p>

Тексты песен со временем строк и слов для отображения как караоке. Поддерживает свои файлы, Spicy Lyrics API (по своему ключу), [LRCLIB](https://lrclib.net) и обычный текст из Яндекс Музыки как запасной вариант.

Текст со временем берётся, только если совпала длина трека (±4 с, а без исполнителя ±2 с). Иначе у ремикса или live-версии строки поедут мимо песни, и вы получите обычный текст.

Сделано [nowplaylab](https://github.com/nowplaylab) для [NowPlaying](https://github.com/nowplaylab/nowplaying-display).

## Установка

```
pip install lrclib-synced
```

Python 3.9+, из зависимостей только aiohttp. На PyPI пакет называется **lrclib-synced** (имя `synced-lyrics` там слишком похоже на чужой проект); в коде по-прежнему `import synced_lyrics`.

## Как пользоваться

```python
import aiohttp, synced_lyrics

async def main():
    async with aiohttp.ClientSession(headers={'User-Agent': 'my-app/1.0'}) as http:
        lyrics = await synced_lyrics.fetch(http, 'Blinding Lights', 'The Weeknd', duration_ms=200040)
        for line in lyrics.synced:          # [{'t': миллисекунды, 'text': строка}], пусто без таймингов
            print(line['t'], line['text'])
        print(lyrics.plain)                 # обычный текст, бывает и без таймингов
        print(lyrics.source)                # 'lrclib', 'yandex' или ''
```

- `fetch()` не бросает исключений на ошибках сети. Если сервис перегружен или не отвечает, запрос повторяется несколько раз; если так и не ответил, у результата `lyrics.complete == False`. Пусто и `complete=True` — текста правда нет; пусто и `complete=False` — «не смогли проверить, спросите позже», такой ответ надолго не запоминайте.
- Названия с приписками вроде `(feat. …)`, `(Prod. by …)` или ` - Remastered 2011` ищутся ещё раз без них (`synced_lyrics.simplify_title()`).
- `use_yandex=False` отключает запасной вариант.
- `local_dirs=['~/Music/Lyrics']` сначала ищет свои файлы, без сети: `Исполнитель - Название.lrc`, `Название - Исполнитель.lrc` или `Название.lrc` (подойдёт и `.txt`, тогда это обычный текст). `.lrc` с любым именем находится по меткам `[ti:]` и `[ar:]`. Если в файле есть `[length:3:34]`, он берётся, только когда длина трека совпадает (±4 с). `lyrics.source` тогда `'file'`. `synced_lyrics.local.find()` и `read()` можно звать и отдельно.
- `parse_lrc()` читает время в виде `[мм:сс]`, `[мм:сс.xx]` и `[мм:сс:xx]`, понимает `[offset:±мс]` и отбрасывает время отдельных слов (`<00:10.80>`), оставляя строку.
- `synced_lyrics.parse_lrc(text)` разбирает любой LRC-текст отдельно.
- В `synced_lyrics.yandex` есть поиск: `find_tracks()`, `same_track()`, `plain_lyrics()`.
- LRCLIB просит присылать свой User-Agent.

## Лицензия

MIT. Проект не связан с LRCLIB и Яндексом.

## Spicy Lyrics (0.4.0)

`fetch(..., spicy_key=ваш_ключ)` включает официальный [Spicy Lyrics API](https://developers.spicylyrics.org/docs). Порядок: свои файлы → Spicy → LRCLIB → Яндекс. Без ключа всё работает по-прежнему. Поиск по названию, исполнителю и длительности; автоматически берутся только точные совпадения с разницей до 4 секунд. Если известен Spotify ID, ISRC или Apple Music ID, передайте `spicy_track_id`.

```python
lyrics = await synced_lyrics.fetch(
    http, title, artist, duration_ms=duration_ms, spicy_key=your_key,
)
```

Ключ передаётся отдельным параметром `spicy_key` из приложения, использующего библиотеку. В самом пакете нет встроенного или общего ключа NowPlaying.

`lyrics.source == 'spicy'` обозначает API, а `lyrics.attribution` — реального поставщика (Apple Music, Spotify или Spicy Lyrics) и авторов синхронизации, когда они есть. Показывайте эти подписи рядом с текстом, со ссылками на профили авторов. Тексты API нельзя кэшировать дольше 30 дней; NowPlaying держит их только в памяти, до 3 дней.

У строк появляются необязательные `end` и `words`: каждый слог/слово содержит `t`, `end` (миллисекунды от начала песни), `start`, `stop` (индексы UTF-16 в тексте строки, как в Android). Части одного слова соединяются без пробелов. Если таймингов слов нет, сохраняется построчная синхронизация, время слов не выдумывается.

Используйте свой ключ. Для публичного приложения нужен клиентский ключ с явно разрешёнными запросами без Origin; секретный ключ в сборку не включайте. При ошибке используются запасные источники, при лимите запросы откладываются. Клиент написан по документации API, код AGPL-аддона PulseSync не копируется.
