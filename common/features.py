"""Feature extraction shared by training (train/train_model.py) and the
backend (backend/ml.py).

This reproduces the original research notebook
(scam-job-posting-detector.ipynb) exactly:

* text = title + company_profile + description + requirements + benefits
* clean(): lowercase, strip HTML, map Kaggle's #URL_/#EMAIL_/#PHONE_ tokens
  to tokurl/tokemail/tokphone, keep a-z only, collapse whitespace
* 10 metadata flags, in this exact order:
  telecommuting, has_company_logo, has_questions, has_url_token,
  has_email_token, has_phone_token, no_profile, no_requirements,
  has_salary, text_len (= log1p(len(clean)) / 10)

For live (non-Kaggle) listings the anonymised #URL_/#EMAIL_/#PHONE_ tokens
do not exist, so the token flags are additionally detected with regex on
real URLs / email addresses / phone numbers in the raw text. On Kaggle
text the regexes do not fire (the tokens were already replaced), so
training behaviour is unchanged.
"""

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
    """The 10 metadata flags (notebook cell 10), in META_COLS order."""
    has_url = ("#URL_" in raw_text) or bool(_URL_RE.search(raw_text))
    has_email = ("#EMAIL_" in raw_text) or bool(_EMAIL_RE.search(raw_text))
    has_phone = ("#PHONE_" in raw_text) or bool(_PHONE_RE.search(raw_text))
    return [
        int(bool(fields.get("telecommuting"))),
        int(bool(fields.get("has_company_logo"))),
        int(bool(fields.get("has_questions"))),
        int(has_url),
        int(has_email),
        int(has_phone),
        int(not _present(fields.get("company_profile"))),
        int(not _present(fields.get("requirements"))),
        int(_present(fields.get("salary_range"))),
        float(np.log1p(len(clean)) / 10),
    ]


def build_features(fields: dict) -> tuple[str, list]:
    """Return (clean_text, meta_feature_vector) for one posting."""
    raw = merge_text(fields)
    clean = clean_text(raw)
    return clean, meta_features(fields, raw, clean)
