"""
Detects the user's message language so Gemini can be instructed
to reply in kind. langdetect covers the major languages listed in
the spec (en, ta, hi, te, ml, kn, fr, de, es, ar, ja, ko, zh, ...).
"""
from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0  # deterministic results

LANGUAGE_NAMES = {
    "en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu",
    "ml": "Malayalam", "kn": "Kannada", "fr": "French", "de": "German",
    "es": "Spanish", "ar": "Arabic", "ja": "Japanese", "ko": "Korean",
    "zh-cn": "Chinese", "zh-tw": "Chinese",
}


def detect_language(text: str) -> str:
    try:
        code = detect(text)
        return code
    except LangDetectException:
        return "en"


def language_instruction(code: str) -> str:
    name = LANGUAGE_NAMES.get(code, code)
    if code == "en":
        return ""
    return f"Reply in {name}, matching the user's language."
