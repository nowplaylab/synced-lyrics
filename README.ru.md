# synced-lyrics

[English](README.md) | **Русский**

Тексты песен со временем каждой строки, чтобы показывать их как караоке. Сначала ищет на [LRCLIB](https://lrclib.net); если там пусто, берёт обычный текст из Яндекс Музыки (без входа в аккаунт).

Текст со временем берётся, только если совпала длина трека (±4 с, а без исполнителя ±2 с). Иначе у ремикса или live-версии строки поедут мимо песни, и вы получите обычный текст.

Сделано [nowplaylab](https://github.com/nowplaylab) для [NowPlaying](https://github.com/nowplaylab/nowplaying-display).

## Установка

```
pip install git+https://github.com/nowplaylab/synced-lyrics@v0.2.0
```

Python 3.9+, из зависимостей только aiohttp.

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
- `synced_lyrics.parse_lrc(text)` разбирает любой LRC-текст отдельно.
- В `synced_lyrics.yandex` есть поиск: `find_tracks()`, `same_track()`, `plain_lyrics()`.
- LRCLIB просит присылать свой User-Agent.

## Лицензия

MIT. Проект не связан с LRCLIB и Яндексом.
