"""Avtomatik tarjima xizmati (admin panelda Auto-translate tugmasi uchun).

Bepul Google Translate (translate.googleapis.com) endpoint'idan foydalanamiz —
API kalit kerak emas. Past hajmda barqaror ishlaydi.
"""

import json
import urllib.parse
import urllib.request

GOOGLE_ENDPOINT = "https://translate.googleapis.com/translate_a/single"

SUPPORTED = {"uz", "ru", "en"}


def _normalize(code):
    if not code:
        return None
    c = str(code).strip().lower()
    if c.startswith("uz"):
        return "uz"
    if c.startswith("ru"):
        return "ru"
    if c.startswith("en"):
        return "en"
    return None


def translate(text, source, target):
    """Bir matnni tarjima qiladi.

    Qaytaradi: tarjima matnini (string) yoki bo'sh bo'lsa asl matnni.
    """
    if not text or not str(text).strip():
        return ""
    src = _normalize(source) or "auto"
    tgt = _normalize(target)
    if not tgt:
        return text
    if src == tgt:
        return text

    params = urllib.parse.urlencode({
        "client": "gtx",
        "sl": src,
        "tl": tgt,
        "dt": "t",
        "q": text,
    })
    url = f"{GOOGLE_ENDPOINT}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Jojo Admin Translate Bot)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
    except Exception:
        return text

    try:
        data = json.loads(raw)
        # Format: [[["TRANSLATION","ORIGINAL",null,null,1]], null, "src"]
        parts = data[0] or []
        return "".join((p[0] or "") for p in parts if p) or text
    except Exception:
        return text


def translate_to_all(text, source):
    """Bitta tildagi matnni boshqa ikki tilga tarjima qiladi.

    Qaytaradi: {"uz": "...", "ru": "...", "en": "..."}
    Source tilga tegmaydi (asl bo'lib qaytadi).
    """
    src = _normalize(source) or "uz"
    out = {"uz": "", "ru": "", "en": ""}
    out[src] = text or ""
    for code in SUPPORTED:
        if code == src:
            continue
        out[code] = translate(text or "", src, code)
    return out
