# synced-lyrics

[English](README.md) | **Русский**

Тексты песен со временем каждой строки, чтобы показывать их как караоке. Сначала ищет на [LRCLIB](https://lrclib.net); если там пусто, берёт обычный текст из Яндекс Музыки (без входа в аккаунт).

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
