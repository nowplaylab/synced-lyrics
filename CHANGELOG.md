# Changes / Изменения

## 0.4.0 — 2026-11-16

- Optional official Spicy Lyrics API: search by title/artist/duration or use a known track id.
- Word/syllable timings in milliseconds with UTF-16 text offsets, plus source and contributor credits.
- Local files retain priority; LRCLIB and Yandex remain fallbacks. No key is bundled in the library.
- API timeouts and cooldown after rate limits or access errors.
- Match multiple player artists against the API artist list; omit unknown optional search fields.

- Официальный Spicy Lyrics API по своему ключу: поиск по названию, исполнителю и длине либо известному ID.
- Тайминги слов/слогов в миллисекундах, индексы UTF-16, подписи источника и авторов.
- Свои файлы имеют приоритет, LRCLIB и Яндекс остаются запасными. Ключ в библиотеку не встроен.
- Ограничение времени запросов и пауза после лимитов или отказа в доступе.
- Список исполнителей сопоставляется со строкой из плеера; неизвестные поля поиска не отправляются пустыми.
