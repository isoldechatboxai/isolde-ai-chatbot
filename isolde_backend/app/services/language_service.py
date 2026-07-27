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
    # FIX: Intercept common English greetings and ambiguous short texts
    # This prevents "hi" from being misclassified as Hindi ("hi")
    cleaned_text = text.strip().lower()
    if cleaned_text in {"hi", "hello", "hey", "good morning", "good evening"}:
        return "en"

    try:
        code = detect(text)
        return code
    except LangDetectException:
        return "en"


def language_instruction(code: str) -> str:
    # FIX: Strictly enforce the whitelist. 
    # If the code (e.g., 'fi') is not in LANGUAGE_NAMES, it returns None.
    name = LANGUAGE_NAMES.get(code)
    
    # If name is None (unsupported language) or code is 'en', default to English (no instruction)
    if not name or code == "en":
        return ""
        
    return f"Reply in {name}, matching the user's language."