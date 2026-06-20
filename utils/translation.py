import re
import sys
import requests
from urllib.parse import quote

from core.config import HEADERS_BROWSER, TIMEOUTS

_LANG_CODE_MAP = {
    "Arabic": "ar", "French": "fr", "Spanish": "es", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Russian": "ru", "Japanese": "ja",
    "Korean": "ko", "Chinese": "zh", "Hindi": "hi", "Turkish": "tr",
    "Dutch": "nl", "Polish": "pl", "Swedish": "sv", "Greek": "el",
    "Czech": "cs", "Romanian": "ro", "Vietnamese": "vi", "Thai": "th",
    "Indonesian": "id", "Malay": "ms",
}

LANGUAGE_NAMES = list(_LANG_CODE_MAP.keys())

def _lang_code(name: str) -> str:
    return _LANG_CODE_MAP.get(name, name[:2])

_ARABIC_RANGE = r'[\u0600-\u06FF]+'
_CJK_RANGE = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+'
_CYRILLIC_RANGE = r'[\u0400-\u04FF]+'
_DEVANAGARI_RANGE = r'[\u0900-\u097F]+'
_JAPANESE_KANA = r'[\u3040-\u309f\u30a0-\u30ff]+'
_KOREAN_RANGE = r'[\uac00-\ud7af]+'

_NON_LATIN_PATTERNS = [
    ('ar', _ARABIC_RANGE),
    ('ja', _JAPANESE_KANA),
    ('ko', _KOREAN_RANGE),
    ('ru', _CYRILLIC_RANGE),
    ('hi', _DEVANAGARI_RANGE),
    ('zh', _CJK_RANGE),
]


def detect_language(text: str) -> str:
    for lang, pattern in _NON_LATIN_PATTERNS:
        if re.search(pattern, text):
            return lang
    return "en"


_RTL_PATTERN = re.compile(r'[\u0600-\u06FF\u0700-\u074F]+')


def rtl_wrap(text: str) -> str:
    if _RTL_PATTERN.search(text):
        return "\u202B" + text + "\u202C"
    return text


def translate_to_english(text: str) -> str:
    if detect_language(text) == "en":
        return text
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text[:500]},
            headers=HEADERS_BROWSER,
            timeout=TIMEOUTS["translate"],
        )
        if r.status_code == 200:
            data = r.json()
            t = "".join(part[0] for part in data[0] if part and part[0])
            if t and detect_language(t) == "en":
                print("  [Translation] Google Translate → English", file=sys.stderr)
                return t.strip()
    except Exception:
        pass
    try:
        from deep_translator import GoogleTranslator
        r = GoogleTranslator(source="auto", target="en").translate(text)
        if r and r.strip() and detect_language(r.strip()) == "en":
            print("  [Translation] deep_translator → English", file=sys.stderr)
            return r.strip()
    except Exception:
        pass
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": "ar|en"},
            headers=HEADERS_BROWSER,
            timeout=TIMEOUTS["translate"],
        )
        if r.status_code == 200:
            t = r.json().get("responseData", {}).get("translatedText", "")
            if t and detect_language(t) == "en" and t.upper() != text.upper():
                print("  [Translation] MyMemory → English", file=sys.stderr)
                return t.strip()
    except Exception:
        pass
    try:
        r = requests.get(
            f"https://lingva.ml/api/v1/ar/en/{quote(text[:500])}",
            headers=HEADERS_BROWSER,
            timeout=TIMEOUTS["translate"],
        )
        if r.status_code == 200:
            t = r.json().get("translation", "")
            if t and detect_language(t) == "en":
                print("  [Translation] Lingva → English", file=sys.stderr)
                return t.strip()
    except Exception:
        pass
    try:
        from ai_backend.llm_handler import ai_chat
        result = ai_chat(
            f"Translate the following text to English. "
            f"Return ONLY the translation, nothing else.\n\n{text}",
            min_len=5,
        )
        if result:
            print("  [Translation] AI chat → English", file=sys.stderr)
            return result.strip()
    except Exception:
        pass
    return text


def translate_text(text: str, target_lang: str) -> str:
    code = _lang_code(target_lang)
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": code, "dt": "t", "q": text[:1000]},
            headers=HEADERS_BROWSER,
            timeout=TIMEOUTS["translate"],
        )
        if r.status_code == 200:
            data = r.json()
            t = "".join(part[0] for part in data[0] if part and part[0])
            if t and t.strip():
                print(f"  [Translation] Google Translate → {target_lang}", file=sys.stderr)
                return t.strip()
    except Exception:
        pass
    try:
        from deep_translator import GoogleTranslator
        r = GoogleTranslator(source="auto", target=code).translate(text)
        if r and r.strip():
            print(f"  [Translation] deep_translator → {target_lang}", file=sys.stderr)
            return r.strip()
    except Exception:
        pass
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": f"en|{code}"},
            headers=HEADERS_BROWSER,
            timeout=TIMEOUTS["translate"],
        )
        if r.status_code == 200:
            t = r.json().get("responseData", {}).get("translatedText", "")
            if t and t.strip() and t.upper() != text.upper():
                print(f"  [Translation] MyMemory → {target_lang}", file=sys.stderr)
                return t.strip()
    except Exception:
        pass
    try:
        r = requests.post(
            "https://libretranslate.com/translate",
            json={"q": text[:500], "source": "en", "target": code},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUTS["translate"],
        )
        if r.status_code == 200:
            t = r.json().get("translatedText", "")
            if t and t.strip():
                print(f"  [Translation] LibreTranslate → {target_lang}", file=sys.stderr)
                return t.strip()
    except Exception:
        pass
    try:
        from ai_backend.llm_handler import ai_chat
        result = ai_chat(
            f"Translate the following text to {target_lang}. "
            f"Return ONLY the translation, nothing else.\n\n{text}",
            min_len=5,
        )
        if result:
            print(f"  [Translation] AI chat → {target_lang}", file=sys.stderr)
            return result.strip()
    except Exception:
        pass
    return text
