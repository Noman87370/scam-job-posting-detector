"""Language detection for the checkers.

The ML model was trained on English postings only, so a result for a
non-English posting would be unreliable. langdetect is seeded so
results are deterministic. Detection returns None when the text is too
short or undetectable; callers treat "unknown" as English (score it)
rather than blocking a posting the detector cannot judge.

For the "Auto" posting-language selector, analyze_language() also
reports a confidence and whether the text looks mixed (German + English)
or unsure, so the caller can ask the user to choose instead of guessing.
"""

from langdetect import DetectorFactory, LangDetectException, detect, detect_langs

DetectorFactory.seed = 0

MIN_TEXT_LEN = 20

# The Auto selector only runs detection on text of at least this length:
# langdetect is unreliable on very short text.
AUTO_MIN_TEXT_LEN = 100

# Below this top-language probability, detection is "unsure".
UNSURE_PROB = 0.5

# If the second language is German/English with at least this
# probability while the top language is the other one, the text looks
# mixed (German + English) and the user should choose.
MIXED_SECOND_PROB = 0.20


def detect_language(text: str) -> str | None:
    """ISO 639-1 code ('en', 'de', ...) or None if undetectable."""
    if not text or len(text.strip()) < MIN_TEXT_LEN:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None
    except Exception:  # noqa: BLE001 — detection must never break scoring
        return None


def analyze_language(text: str, min_len: int = AUTO_MIN_TEXT_LEN) -> dict:
    """Detect language with confidence, for the Auto selector.

    Returns {"code", "confidence", "mixed", "unsure"}: code is the top
    ISO 639-1 code (or None), confidence its probability (0.0-1.0),
    mixed True when German and English both look present, unsure True
    when detection is too weak to trust.
    """
    result = {"code": None, "confidence": 0.0, "mixed": False, "unsure": True}
    if not text or len(text.strip()) < min_len:
        return result
    try:
        langs = detect_langs(text)
    except LangDetectException:
        return result
    except Exception:  # noqa: BLE001 — detection must never break scoring
        return result
    if not langs:
        return result
    top = langs[0]
    result["code"] = top.lang
    result["confidence"] = round(float(top.prob), 3)
    result["unsure"] = float(top.prob) < UNSURE_PROB
    if len(langs) > 1:
        second = langs[1]
        pair = {top.lang, second.lang}
        if pair == {"de", "en"} and float(second.prob) >= MIXED_SECOND_PROB:
            result["mixed"] = True
    return result


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


def language_name(code: str | None) -> str:
    """Human-readable name for an ISO code, or the code itself."""
    if not code:
        return "unknown"
    return LANGUAGE_NAMES.get(code, code)
