import os
import re
import json
import time
import hashlib
import io
import contextlib
import warnings
import requests
from urllib.parse import quote
from duckduckgo_search import DDGS

import duckduckgo_search.duckduckgo_search as _ddgs_mod
if _ddgs_mod.warnings.simplefilter.__name__ != "_suppress_rename_warning":
    _original_simplefilter = _ddgs_mod.warnings.simplefilter
    def _suppress_rename_warning(action, category=Warning, append=False):
        if action == "always" and category is Warning:
            return
        return _original_simplefilter(action, category, append)
    _ddgs_mod.warnings.simplefilter = _suppress_rename_warning
    _ddgs_mod.DDGS.__init__.__globals__["warnings"].simplefilter = _suppress_rename_warning

from core.config import TIMEOUTS
from utils.logger import logger

_JUNK_PATTERNS = re.compile(
    r"(sorry|cannot|i can.t|as an ai|i don.t|unavailable|"
    r"i'm not able|i am not able|i cannot|not possible|i apologize)",
    re.IGNORECASE,
)


def _is_valid_ai_response(text: str, min_len: int = 20) -> bool:
    if not text or len(text.strip()) < min_len:
        return False
    if _JUNK_PATTERNS.search(text[:150]):
        return False
    return True


_AI_CACHE: dict = {}
_CACHE_TTL = 300


def _try_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ""
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUTS["ai"],
        )
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.warning(f"Gemini API failed: {exc}")
    return ""


def _try_groq(prompt: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return ""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": prompt}],
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=TIMEOUTS["ai"],
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning(f"Groq API failed: {exc}")
    return ""


def _try_ddgs_chat(prompt: str) -> str:
    try:
        with DDGS() as ddgs:
            return ddgs.chat(prompt, model="gpt-4o-mini") or ""
    except Exception as exc:
        logger.warning(f"DDGS chat failed: {exc}")
        return ""


def _try_ddgs_claude(prompt: str) -> str:
    try:
        with DDGS() as ddgs:
            return ddgs.chat(prompt, model="claude-3-haiku") or ""
    except Exception as exc:
        logger.warning(f"DDGS Claude failed: {exc}")
        return ""


def _try_pollinations(prompt: str) -> str:
    try:
        r = requests.post(
            "https://text.pollinations.ai/openai",
            json={
                "model": "openai",
                "messages": [{"role": "user", "content": prompt}],
                "seed": 42,
            },
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUTS["ai"],
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning(f"Pollinations API failed: {exc}")
    try:
        r = requests.get(
            f"https://text.pollinations.ai/{quote(prompt[:400])}",
            timeout=TIMEOUTS["ai"],
        )
        if r.status_code == 200 and len(r.text) > 5:
            return r.text.strip()
    except Exception as exc:
        logger.warning(f"Pollinations GET failed: {exc}")
    return ""


def _try_g4f(prompt: str) -> str:
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            import g4f
            models = [
                g4f.models.default,
                "gpt-4o-mini",
                "gpt-4o",
                "gpt-4",
                "gpt-3.5-turbo",
                "claude-3-haiku",
                "llama-3-70b",
            ]
            for model in models:
                try:
                    result = g4f.ChatCompletion.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    result_str = str(result).strip()
                    if result_str and _is_valid_ai_response(result_str):
                        return result_str
                except Exception:
                    continue
    except Exception as exc:
        logger.warning(f"g4f failed: {exc}")
    return ""


def ai_chat(prompt: str, min_len: int = 20) -> str:
    cache_key = hashlib.md5(prompt.encode()).hexdigest()
    if cache_key in _AI_CACHE:
        cached_result, ts = _AI_CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return cached_result
    for fn in (_try_gemini, _try_groq, _try_ddgs_chat, _try_ddgs_claude, _try_pollinations, _try_g4f):
        try:
            r = fn(prompt)
            if _is_valid_ai_response(r, min_len):
                _AI_CACHE[cache_key] = (r, time.time())
                return r
        except Exception as exc:
            logger.warning(f"AI backend {fn.__name__} error: {exc}")
            continue
    return ""


def safe_parse_ai_json(raw: str, expected_type=dict):
    if not raw:
        return None
    clean = re.sub(r'```(?:json)?|```', '', raw).strip()
    try:
        result = json.loads(clean)
        if isinstance(result, expected_type):
            return result
    except Exception:
        pass
    pattern = r'\[.*?\]' if expected_type == list else r'\{.*?\}'
    match = re.search(pattern, clean, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, expected_type):
                return result
        except Exception:
            pass
    try:
        fixed = re.sub(r',\s*([}\]])', r'\1', clean)
        result = json.loads(fixed)
        if isinstance(result, expected_type):
            return result
    except Exception:
        pass
    try:
        open_ch = '[' if expected_type == list else '{'
        close_ch = ']' if expected_type == list else '}'
        depth, start = 0, -1
        for idx, ch in enumerate(clean):
            if ch == open_ch:
                if depth == 0:
                    start = idx
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0 and start != -1:
                    result = json.loads(clean[start:idx + 1])
                    if isinstance(result, expected_type):
                        return result
                    break
    except Exception:
        pass
    return None
