"""Language detection for the English-only model.

The model was trained on English postings only, so a result for a
non-English posting would be unreliable. langdetect is seeded so
results are deterministic. Detection returns None when the text is too
short or undetectable; callers treat "unknown" as English (score it)
rather than blocking a posting the detector cannot judge.
"""

from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

MIN_TEXT_LEN = 20


def detect_language(text: str):
    """ISO 639-1 code ('en', 'de', ...) or None if undetectable."""
    if not text or len(text.strip()) < MIN_TEXT_LEN:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None
    except Exception:  # noqa: BLE001 — detection must never break scoring
        return None


def is_english(text: str) -> bool:
    """True when the text is English, or its language cannot be told."""
    lang = detect_language(text)
    return lang is None or lang == "en"


# Short display names for the languages the detector may return.
LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "ru": "Russian",
    "uk": "Ukrainian",
    "ar": "Arabic",
    "hi": "Hindi",
    "zh-cn": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
}


def language_name(code) -> str:
    """Human-readable name for an ISO code, or the code itself."""
    if not code:
        return "unknown"
    return LANGUAGE_NAMES.get(code, code)
