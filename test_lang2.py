import re
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0
_RTL_PATTERN = re.compile(r'[\u0600-\u06FF\u0700-\u074F]+')

def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "en"
    try:
        if _RTL_PATTERN.search(text):
            return "ar"
        lang = detect(text)
        if lang.startswith("zh"):
            return "zh"
        return lang
    except Exception as e:
        return "en"

print("russian:", detect_language("привет мир"))
print("chinese:", detect_language("你好世界"))
print("mixed:", detect_language("hello مرحبا"))
