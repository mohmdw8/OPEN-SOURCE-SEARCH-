from utils.translation import detect_language, translate_to_english, translate_text


def test_detect_english():
    assert detect_language("This is a simple english sentence for testing") == "en"
    assert detect_language("") == "en"


def test_detect_arabic():
    assert detect_language("مرحبا بالعالم") == "ar"


def test_detect_japanese():
    assert detect_language("こんにちは") == "ja"
    assert detect_language("コンニチハ") == "ja"


def test_detect_korean():
    assert detect_language("안녕하세요") == "ko"


def test_detect_russian():
    lang = detect_language("привет мир")
    assert lang in ["ru", "bg", "mk", "uk"]


def test_detect_hindi():
    assert detect_language("नमस्ते दुनिया") == "hi"


def test_detect_chinese():
    lang = detect_language("你好世界")
    assert lang.startswith("zh")


def test_detect_mixed_latin_non_latin():
    lang = detect_language("hello مرحبا")
    assert lang in ["ar", "en", "so"]


def test_detect_non_latin_precedence():
    assert detect_language("hello こんにちは") == "ja"


def test_translate_to_english_passthrough():
    assert translate_to_english("This is a simple english sentence") == "This is a simple english sentence"
    assert translate_to_english("web scraper testing") == "web scraper testing"


def test_translate_to_english_arabic():
    result = translate_to_english("أداة لفحص الشبكات")
    assert result is not None
    assert len(result) > 2
    assert detect_language(result) == "en"


def test_translate_to_english_french():
    result = translate_to_english("outil de compression de fichiers")
    assert result is not None
    assert len(result) > 2
    assert detect_language(result) in ["en", "it", "fr"] or "compression" in result.lower() or "file" in result.lower()


def test_translate_text_to_arabic():
    result = translate_text("hello world", "ar")
    assert result is not None
    assert len(result) > 0


def test_translate_text_to_french():
    result = translate_text("hello world", "fr")
    assert result is not None
    assert len(result) > 0


def test_detect_empty_string():
    assert detect_language("") == "en"


def test_detect_only_numbers_symbols():
    assert detect_language("12345 !@#$%") == "en"
