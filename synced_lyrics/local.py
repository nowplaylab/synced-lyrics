"""Свои тексты из файлов: .lrc (со временем строк) или .txt (просто текст) в папках на компьютере.

    path = synced_lyrics.local.find(['~/Music/Lyrics'], 'Ночной маршрут', 'Кассета', duration_ms=214000)
    lyrics = synced_lyrics.local.read(path)

Как файл находится (без учёта регистра, лишних пробелов и знаков):
  * по имени: «Исполнитель - Название.lrc», «Название - Исполнитель.lrc» или «Название.lrc»;
  * по меткам внутри LRC: [ti:Название] и [ar:Исполнитель].
Если в LRC есть [length:3:34] и длина трека известна, файл берётся, только когда они сходятся (±4 с).
Папки просматриваются с подпапками (до двух уровней), .lrc важнее .txt.
"""
import os
import re

from . import Lyrics, parse_lrc, simplify_title

EXTS = ('.lrc', '.txt')
MAX_FILES = 5000          # не читать бесконечно огромную папку
LENGTH_LIMIT = 4000


def _norm(text):
    text = (text or '').lower().replace('ё', 'е')
    return re.sub(r'[\W_]+', ' ', text).strip()


def _read_text(path):
    with open(path, 'rb') as f:
        raw = f.read(2_000_000)
    for enc in ('utf-8-sig', 'cp1251'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode('utf-8', 'replace')
    return text.replace('\r\n', '\n').replace('\r', '\n')   # файлы из Windows и старых Mac


def _tags(text):
    """Метки LRC из шапки: {'ti': ..., 'ar': ..., 'length': ...}."""
    return {k.lower(): v.strip() for k, v in re.findall(r'^\s*\[([a-zA-Z]+):([^\]]*)\]\s*$', text, re.M)}


def _length_ms(value):
    m = re.fullmatch(r'\s*(\d+):(\d+(?:\.\d+)?)\s*', value or '')
    return int((int(m.group(1)) * 60 + float(m.group(2))) * 1000) if m else 0


def _files(dirs):
    n = 0
    for d in dirs or ():
        root = os.path.expanduser(str(d))
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for cur, subdirs, files in os.walk(root):
            if cur.count(os.sep) - base_depth >= 2:
                subdirs[:] = []
            for name in files:
                if name.lower().endswith(EXTS):
                    yield os.path.join(cur, name)
                    n += 1
                    if n >= MAX_FILES:
                        return


def find(dirs, title, artist='', duration_ms=0):
    """Путь к подходящему файлу или None."""
    titles = {_norm(title), _norm(simplify_title(title))} - {''}
    if not titles:
        return None
    art = _norm(artist)
    names = set()
    for t in titles:
        names.add(t)
        if art:
            names.update({f'{art} {t}', f'{t} {art}'})
    best = None   # (приоритет, путь): меньше — лучше
    for path in _files(dirs):
        stem, ext = os.path.splitext(os.path.basename(path))
        rank = 0 if ext.lower() == '.lrc' else 1
        hit = _norm(stem) in names
        if not hit and ext.lower() == '.lrc':
            try:
                tags = _tags(_read_text(path))
            except OSError:
                continue
            hit = _norm(tags.get('ti')) in titles and (not art or not tags.get('ar') or _norm(tags.get('ar')) == art)
            rank += 2                     # совпадение по меткам — после совпадения по имени
        if not hit:
            continue
        if ext.lower() == '.lrc' and duration_ms:
            try:
                length = _length_ms(_tags(_read_text(path)).get('length'))
            except OSError:
                continue
            if length and abs(length - duration_ms) > LENGTH_LIMIT:
                continue
        if best is None or rank < best[0]:
            best = (rank, path)
    return best[1] if best else None


def read(path):
    """Lyrics из файла: .lrc — со временем строк, .txt — обычный текст. source='file'."""
    text = _read_text(path)
    if path.lower().endswith('.lrc'):
        synced = parse_lrc(text)
        plain = '\n'.join(l['text'] for l in synced) if synced else re.sub(r'\[[^\]]*\]', '', text).strip()
        return Lyrics(synced, plain, 'file')
    return Lyrics([], text.strip(), 'file')
