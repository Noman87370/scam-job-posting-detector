"""Feature extraction shared by training (train/train_model.py) and the
backend (backend/ml.py).

This reproduces the original research notebook
(scam-job-posting-detector.ipynb) exactly:

* text = title + company_profile + description + requirements + benefits
* real URLs, email addresses and phone numbers are first converted to
  the Kaggle-style placeholders (#URL_x# / #EMAIL_x# / #PHONE_x#), so
  that live input behaves like the anonymised training data
* clean(): lowercase, strip HTML, map #URL_/#EMAIL_/#PHONE_ tokens to
  tokurl/tokemail/tokphone, keep a-z only, collapse whitespace
* 10 metadata flags, in this exact order:
  telecommuting, has_company_logo, has_questions, has_url_token,
  has_email_token, has_phone_token, no_profile, no_requirements,
  has_salary, text_len (= log1p(len(clean)) / 10)

The has_*_token flags are presence of the placeholder in the
(anonymised) text — exactly the notebook's definition. An earlier
version detected them with regex on the raw text instead; on the Kaggle
data that flagged 3,070 rows for phone (regex matches dates and long
numbers) versus 527 rows with a real #PHONE_ placeholder, and 515 rows
for URL versus 5,621 with a placeholder, so the flags did not match the
notebook. The anonymisation step below makes live input match the
notebook definition: a flag is 1 exactly when its tok* token is in the
cleaned text.
"""

import hashlib
import re

import numpy as np

TEXT_COLS = ["title", "company_profile", "description", "requirements", "benefits"]

META_COLS = [
    "telecommuting",
    "has_company_logo",
    "has_questions",
    "has_url_token",
    "has_email_token",
    "has_phone_token",
    "no_profile",
    "no_requirements",
    "has_salary",
    "text_len",
]

_URL_RE = re.compile(r"(https?://|www\.)\S+|[\w.+-]+\.[a-z]{2,}/\S*", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
# Dates look like phone numbers to _PHONE_RE ("2026-11-25", "25.11.2026");
# they are not phone numbers, so they are left untouched.
_DATE_RE = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b")


def _placeholder(kind: str, match_text: str) -> str:
    """Kaggle-style placeholder, e.g. #URL_a1b2c3#.

    The hex digest keeps the placeholder in the shape clean_text()
    recognises (#url_[a-f0-9]+#), and equal inputs map to equal tokens.
    """
    digest = hashlib.md5(match_text.encode("utf-8")).hexdigest()[:6]
    return f"#{kind}_{digest}#"


def anonymize_text(t: str) -> str:
    """Replace real URLs, emails and phone numbers with placeholders.

    Runs before clean_text(), so the placeholders become the tokurl /
    tokemail / tokphone tokens the model was trained on. Kaggle text is
    already anonymised, so this is a no-op on training data (except for
    the few real URLs the dataset left in, which are now handled the
    same way as in the notebook's anonymisation).
    """
    t = _URL_RE.sub(lambda m: _placeholder("URL", m.group(0)), t)
    t = _EMAIL_RE.sub(lambda m: _placeholder("EMAIL", m.group(0)), t)

    def _phone_sub(m):
        s = m.group(0)
        if _DATE_RE.search(s):
            return s
        return _placeholder("PHONE", s)

    return _PHONE_RE.sub(_phone_sub, t)


def clean_text(t: str) -> str:
    """Notebook cell 8, verbatim."""
    t = t.lower()
    t = re.sub(r"<[^>]+>", " ", t)  # HTML tags
    t = re.sub(r"#url_[a-f0-9]+#", " tokurl ", t)
    t = re.sub(r"#email_[a-f0-9]+#", " tokemail ", t)
    t = re.sub(r"#phone_[a-f0-9]+#", " tokphone ", t)
    t = re.sub(r"[^a-z\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def merge_text(fields: dict) -> str:
    """Join the five text columns with a space (notebook cell 7)."""
    return " ".join(str(fields.get(c) or "") for c in TEXT_COLS)


def _present(v) -> bool:
    """True if a field value is really there (not None / NaN / blank)."""
    if v is None:
        return False
    if isinstance(v, float) and v != v:  # NaN
        return False
    return bool(str(v).strip())


def meta_features(fields: dict, raw_text: str, clean: str) -> list:
    """The 10 metadata flags (notebook cell 10), in META_COLS order.

    raw_text is the ANONYMISED merged text (placeholders present), so
    the has_*_token flags are exactly "placeholder present", as in the
    notebook. fields may also carry an explicit "has_salary" boolean
    (from the "salary stated" checkbox in the form); otherwise the flag
    is presence of a salary_range value, as in training.
    """
    has_url = "#URL_" in raw_text
    has_email = "#EMAIL_" in raw_text
    has_phone = "#PHONE_" in raw_text
    return [
        int(bool(fields.get("telecommuting"))),
        int(bool(fields.get("has_company_logo"))),
        int(bool(fields.get("has_questions"))),
        int(has_url),
        int(has_email),
        int(has_phone),
        int(not _present(fields.get("company_profile"))),
        int(not _present(fields.get("requirements"))),
        int(bool(fields.get("has_salary")) or _present(fields.get("salary_range"))),
        float(np.log1p(len(clean)) / 10),
    ]


def build_features(fields: dict) -> tuple[str, list]:
    """Return (clean_text, meta_feature_vector) for one posting."""
    raw = merge_text(fields)
    anon = anonymize_text(raw)
    clean = clean_text(anon)
    return clean, meta_features(fields, anon, clean)
