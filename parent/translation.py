"""Avtomatik tarjima xizmati — uz / ru / en.

Strategiya:
  1) Bepul Google Translate (translate.googleapis.com) — API kalit kerak emas.
     Bir requestga taxminan 5000 ta belgi cheklovi bor — uzun matnlarni
     `_split_chunks` orqali bo'lib yuboramiz.
  2) Agar Google qaytarmasin (rate limit, network), LibreTranslate'ga
     fallback qilamiz (`LIBRETRANSLATE_URL` env'da bo'lsa). Mavjud bo'lmasa,
     asl matn qaytariladi va tarjima keyingi safar urunib ko'riladi.

Foydalanish:
    from parent.translation import translate, translate_to_all
    translate("Salom", "uz", "ru")   # -> "Привет"
    translate_to_all("Salom", "uz")  # -> {"uz": "Salom", "ru": "...", "en": "..."}

Uzunligi xohlagancha bo'lishi mumkin — chunklarga avtomatik bo'linadi.
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request

GOOGLE_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
LIBRETRANSLATE_URL = os.environ.get(
    "LIBRETRANSLATE_URL", "https://libretranslate.de/translate"
).rstrip("/")
LIBRETRANSLATE_API_KEY = os.environ.get("LIBRETRANSLATE_API_KEY", "")

SUPPORTED = {"uz", "uz_cyrl", "ru", "en"}
# Google bepul endpoint'i bitta requestda taxminan 5000 belgini ko'tara oladi.
# 4500 ga cheklab xavfsiz tarafda turamiz.
_CHUNK_LIMIT = 4500
_USER_AGENT = "Mozilla/5.0 (Jojo Admin Translate Bot)"


def _normalize(code):
    if not code:
        return None
    c = str(code).strip().lower().replace("-", "_")
    # uz_cyrl / uz-cyrl / uz_cyr / cyrillic — Kirill uzbek
    if c in ("uz_cyrl", "uz_cyr", "uz_cy", "uzc", "uzcyrl"):
        return "uz_cyrl"
    if c.startswith("uz_") and "cyr" in c:
        return "uz_cyrl"
    # uz_latn / uz / uzbek — Lotin uzbek (default)
    if c.startswith("uz"):
        return "uz"
    if c.startswith("ru"):
        return "ru"
    if c.startswith("en"):
        return "en"
    return None


# ----------------------------------------------------------------------------
# Lotin ↔ Kirill transliteratsiyasi (O‘zbek tili)
# ----------------------------------------------------------------------------
# Tartib muhim: ko'p belgili kombinatsiyalarni (sh, ch, yo, ya...) bitta
# belgilarning oldiga qo'yamiz, aks holda "sh" → "сҳ" bo'lib qoladi.

_LATIN_TO_CYRL_PAIRS = [
    # Apostrof variantlari — qattiq belgi
    ("o‘", "ў"), ("O‘", "Ў"),
    ("o'", "ў"), ("O'", "Ў"),
    ("o`", "ў"), ("O`", "Ў"),
    ("g‘", "ғ"), ("G‘", "Ғ"),
    ("g'", "ғ"), ("G'", "Ғ"),
    ("g`", "ғ"), ("G`", "Ғ"),
    # Ko'p harfli
    ("sh", "ш"), ("Sh", "Ш"), ("SH", "Ш"),
    ("ch", "ч"), ("Ch", "Ч"), ("CH", "Ч"),
    ("yo", "ё"), ("Yo", "Ё"), ("YO", "Ё"),
    ("yu", "ю"), ("Yu", "Ю"), ("YU", "Ю"),
    ("ya", "я"), ("Ya", "Я"), ("YA", "Я"),
    ("ye", "е"), ("Ye", "Е"), ("YE", "Е"),
    ("ng", "нг"), ("Ng", "Нг"), ("NG", "НГ"),
    ("ts", "ц"), ("Ts", "Ц"), ("TS", "Ц"),
]
_LATIN_TO_CYRL_SINGLE = {
    "a": "а", "b": "б", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "ҳ",
    "i": "и", "j": "ж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з", "c": "к",
}


def latin_to_cyrillic(text):
    """O‘zbek tilidagi lotin matnni Kirill yozuviga aylantiradi.

    Idempotent emas: Kirill matnni qayta o'tkazsa, ASCII bo'lmagani sabab
    ko'p belgilarga tegmaydi.
    """
    if not text:
        return ""
    s = str(text)
    for lat, cyr in _LATIN_TO_CYRL_PAIRS:
        s = s.replace(lat, cyr)
    out = []
    for ch in s:
        lower = ch.lower()
        mapped = _LATIN_TO_CYRL_SINGLE.get(lower)
        if mapped is None:
            out.append(ch)
            continue
        out.append(mapped.upper() if ch.isupper() else mapped)
    return "".join(out)


_CYRL_TO_LATIN_PAIRS = [
    ("ў", "o‘"), ("Ў", "O‘"),
    ("ғ", "g‘"), ("Ғ", "G‘"),
    ("ш", "sh"), ("Ш", "Sh"),
    ("ч", "ch"), ("Ч", "Ch"),
    ("ё", "yo"), ("Ё", "Yo"),
    ("ю", "yu"), ("Ю", "Yu"),
    ("я", "ya"), ("Я", "Ya"),
    ("ц", "ts"), ("Ц", "Ts"),
]
_CYRL_TO_LATIN_SINGLE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ҳ": "h", "қ": "q", "ъ": "ʼ", "ь": "",
}


def cyrillic_to_latin(text):
    """Kirill o‘zbek matnini lotin yozuviga aylantiradi."""
    if not text:
        return ""
    s = str(text)
    for cyr, lat in _CYRL_TO_LATIN_PAIRS:
        s = s.replace(cyr, lat)
    out = []
    for ch in s:
        lower = ch.lower()
        mapped = _CYRL_TO_LATIN_SINGLE.get(lower)
        if mapped is None:
            out.append(ch)
            continue
        # capitalize map qiymatini (multi-char) muvofiqlashtirish
        out.append(mapped.title() if ch.isupper() and len(mapped) > 1 else
                   (mapped.upper() if ch.isupper() else mapped))
    return "".join(out)


def _hard_split(text, limit):
    """`text`ni `limit` uzunligida qismlarga aniq bo'ladi — so'z chegarasi
    yo'q bo'lsa ham hech narsa yo'qotmaymiz."""
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def _split_chunks(text, limit=_CHUNK_LIMIT):
    """Matnni `limit` belgidan kichik bo'laklarga bo'ladi.

    Birinchi navbatda paragraflar (\n\n) bo'yicha, so'ng gaplar (./?!),
    so'ng bo'shliqlar bo'yicha, oxir-oqibat zarurat tug'ilsa belgi-belgi
    bo'yicha bo'lamiz. Hech qachon belgilarni yo'qotmaymiz.
    """
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks = []
    buf = ""

    def flush():
        nonlocal buf
        if buf:
            chunks.append(buf)
            buf = ""

    def append_piece(piece):
        nonlocal buf
        if not piece:
            return
        if len(piece) > limit:
            # Bu darajada piece hali ham juda uzun — sub-bo'lakka tushiramiz
            for sub in _hard_split(piece, limit):
                if len(buf) + len(sub) <= limit:
                    buf += sub
                else:
                    flush()
                    buf = sub
            return
        if len(buf) + len(piece) <= limit:
            buf += piece
        else:
            flush()
            buf = piece

    # Birinchi pog'ona: paragraflar
    paragraphs = re.split(r"(\n\s*\n)", text)
    for paragraph in paragraphs:
        if len(paragraph) <= limit:
            append_piece(paragraph)
            continue
        # Paragraf uzun — gaplarga
        sentences = re.split(r"([\.\!\?]+\s+)", paragraph)
        for sentence in sentences:
            if len(sentence) <= limit:
                append_piece(sentence)
                continue
            # Gap ham uzun — bo'shliq bo'yicha
            words = re.split(r"(\s+)", sentence)
            for word in words:
                append_piece(word)

    flush()
    return chunks


def _google_translate_chunk(text, src, tgt, timeout=8):
    """Google bepul endpointi orqali bitta chunk tarjima qiladi."""
    params = urllib.parse.urlencode({
        "client": "gtx",
        "sl": src or "auto",
        "tl": tgt,
        "dt": "t",
        "q": text,
    })
    url = f"{GOOGLE_ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    # [[["TRANSLATION","ORIGINAL",null,null,1], ...], ...]
    parts = data[0] or []
    out = "".join((p[0] or "") for p in parts if p)
    return out or text


def _libretranslate_chunk(text, src, tgt, timeout=10):
    """LibreTranslate fallback. URL env bilan o'rnatilgan bo'lishi shart."""
    if not LIBRETRANSLATE_URL:
        return text
    payload = {
        "q": text,
        "source": src or "auto",
        "target": tgt,
        "format": "text",
    }
    if LIBRETRANSLATE_API_KEY:
        payload["api_key"] = LIBRETRANSLATE_API_KEY
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LIBRETRANSLATE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    return data.get("translatedText") or text


def _translate_chunk(text, src, tgt):
    """Bir chunkni tarjima qilishga harakat qiladi: Google -> LibreTranslate.

    Network/timeout xatolarini yutadi va asl matnni qaytaradi.
    """
    # 1) Google (2 marta retry)
    for attempt in range(2):
        try:
            out = _google_translate_chunk(text, src, tgt)
            if out and out.strip():
                return out
        except Exception:
            if attempt == 0:
                time.sleep(0.4)
            continue
    # 2) LibreTranslate fallback
    try:
        out = _libretranslate_chunk(text, src, tgt)
        if out and out.strip():
            return out
    except Exception:
        pass
    return text


def translate(text, source, target):
    """Bir matnni tarjima qiladi (uzunligidan qat'iy nazar).

    Qaytaradi: tarjima matnini (string) yoki bo'sh bo'lsa asl matnni.
    `uz_cyrl` mahsus til — lotin↔kirill o'tkazish mexanik tarzda
    transliteratsiya qilinadi (tarmoq so'rovi yo'q).
    """
    if not text or not str(text).strip():
        return ""
    src = _normalize(source)
    tgt = _normalize(target)
    if not tgt:
        return text
    if src == tgt:
        return text

    text = str(text)

    # Lotin ↔ Kirill — mexanik transliteratsiya
    if src == "uz" and tgt == "uz_cyrl":
        return latin_to_cyrillic(text)
    if src == "uz_cyrl" and tgt == "uz":
        return cyrillic_to_latin(text)
    # Kirilldan ru/en ga: avval Lotin'ga aylantirib, keyin tarjima
    if src == "uz_cyrl" and tgt in ("ru", "en"):
        latin = cyrillic_to_latin(text)
        return translate(latin, "uz", tgt)
    # ru/en'dan Kirill'ga: avval uz lotin'ga tarjima, keyin transliteratsiya
    if src in ("ru", "en") and tgt == "uz_cyrl":
        latin = translate(text, src, "uz")
        return latin_to_cyrillic(latin)

    if len(text) <= _CHUNK_LIMIT:
        return _translate_chunk(text, src, tgt)

    # Uzun matn — chunklarga bo'lib tarjima, keyin yana qo'shamiz.
    parts = _split_chunks(text, _CHUNK_LIMIT)
    translated_parts = []
    for i, chunk in enumerate(parts):
        if not chunk:
            translated_parts.append(chunk)
            continue
        translated_parts.append(_translate_chunk(chunk, src, tgt))
        # Google/Libre'ni juda tez urmaslik uchun engil pauza
        if i < len(parts) - 1:
            time.sleep(0.15)
    return "".join(translated_parts)


def translate_to_all(text, source):
    """Bitta tildagi matnni boshqa qolgan tillarga tarjima qiladi.

    Qaytaradi: {"uz": "...", "uz_cyrl": "...", "ru": "...", "en": "..."}
    Source tilga tegmaydi (asl bo'lib qaytadi).
    """
    src = _normalize(source) or "uz"
    out = {"uz": "", "uz_cyrl": "", "ru": "", "en": ""}
    out[src] = text or ""
    for code in SUPPORTED:
        if code == src:
            continue
        out[code] = translate(text or "", src, code)
    return out


def fill_missing(values, source):
    """`values = {"uz": ..., "ru": ..., "en": ...}` — bo'sh maydonlarni
    `source` tilidagi qiymatdan tarjima qilib to'ldiradi.

    Qo'lda kiritilgan qiymatlar saqlab qoladi.
    """
    src = _normalize(source) or "uz"
    base = (values.get(src) or "").strip()
    if not base:
        return values
    result = dict(values)
    for code in SUPPORTED:
        if code == src:
            continue
        existing = (result.get(code) or "").strip()
        if existing:
            continue
        result[code] = translate(base, src, code)
    return result
