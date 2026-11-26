"""Pydantic schemas for the API.

The checker returns a decision score and a risk band — never a
probability presented as a "% chance of scam". The fraud probability
is kept on stored jobs only, for sorting; it is not part of the
checker response.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .ml import DECISION_THRESHOLD

DISCLAIMER = (
    "This is a statistical estimate, not proof. The model misses about "
    "1 in 4 scams and can flag real postings."
)

DISCLAIMER_DE = (
    "Dies ist eine statistische Schätzung, kein Beweis. Das Modell "
    "übersieht etwa jede vierte betrügerische Anzeige und kann echte "
    "Anzeigen fälschlich markieren."
)

# Section 5 labels (both languages; the frontend picks by UI language).
ML_METHOD_LABEL_EN = (
    "Machine-learning model, evaluated on English postings: "
    "precision 93.1%, recall 76.6%."
)
ML_METHOD_LABEL_DE = (
    "Modell für maschinelles Lernen, evaluiert auf englischen "
    "Stellenanzeigen: Präzision 93,1 %, Recall 76,6 %."
)
DE_METHOD_LABEL_EN = (
    "Rule-based check, based on warnings from German consumer advice "
    "centers. Not validated on labelled data."
)
DE_METHOD_LABEL_DE = (
    "Regelbasierte Prüfung, gestützt auf Warnungen deutscher "
    "Verbraucherzentralen. Nicht an gelabelten Daten validiert."
)


class JobOut(BaseModel):
    id: int
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    category: str
    posted_at: Optional[datetime] = None
    fetched_at: datetime
    fraud_probability: float
    decision_score: Optional[float] = None
    risk_band: str
    language: Optional[str] = None
    indicators: dict = {}
    expired: bool

    model_config = ConfigDict(from_attributes=True)


class JobsPage(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[JobOut]


class PredictIn(BaseModel):
    title: str = ""
    company: str = ""
    description: str = ""
    requirements: str = ""
    benefits: str = ""
    company_profile: str = ""
    location: str = ""
    salary_range: str = ""
    telecommuting: bool = False
    has_company_logo: bool = False
    has_questions: bool = False
    # "Salary stated in the posting" checkbox; has_salary is also set
    # when a salary_range value is given (see common.features).
    has_salary: bool = False
    # Posting language: "auto" (detect), "de" or "en".
    posting_language: str = "auto"
    # User-reported context for the German checker (checkbox ids from
    # backend/rules_de.py CHECKBOXES): "unsolicited", "asked_id",
    # "asked_bank_or_fee", "contact_messenger".
    context_flags: list[str] = []


class Indicator(BaseModel):
    code: str
    label: str
    detail: str
    present: bool


class Contribution(BaseModel):
    feature: str
    contribution: float


class DeRuleMatch(BaseModel):
    rule_id: str
    category: str
    severity: str  # critical | strong | mild (after any downgrade)
    explanation_de: str
    explanation_en: str
    evidence: str  # the matched sentence, raw text (the frontend escapes it)
    downgraded: bool = False


class DeCheckboxApplied(BaseModel):
    id: str
    severity: str
    text_de: str
    text_en: str


class PredictOut(BaseModel):
    # ML path fields (None/empty when the result comes from another path).
    decision_score: Optional[float] = None
    risk_band: str = ""  # high | some | few
    risk_label: str = ""  # "High risk" | "Some warning signs" | "Few warning signs"
    threshold: float = DECISION_THRESHOLD  # decision-function score for "high risk"
    top_raising: list[Contribution] = []
    top_lowering: list[Contribution] = []
    indicators: list[Indicator] = []
    language: Optional[str] = None
    language_ok: bool = True
    language_message: str = ""
    disclaimer: str = DISCLAIMER
    disclaimer_de: str = DISCLAIMER_DE
    # Which path produced this result: "ml" | "de" | "needs_choice" |
    # "unsupported". For "needs_choice"/"unsupported" there is no risk
    # level — the user must pick the posting language first.
    path: str = "ml"
    detected_language: Optional[str] = None
    detected_confidence: float = 0.0
    mixed: bool = False
    method_label_de: str = ""
    method_label_en: str = ""
    # German rule-based path fields (empty when path != "de").
    de_band: str = ""
    de_band_label_de: str = ""
    de_band_label_en: str = ""
    de_critical: int = 0
    de_strong: int = 0
    de_mild: int = 0
    de_matched: list[DeRuleMatch] = []
    de_checkboxes: list[DeCheckboxApplied] = []
    de_advice: bool = False
    de_advice_link: str = ""
    de_few_note_de: str = ""
    de_few_note_en: str = ""


class IngestOut(BaseModel):
    source: str
    fetched: int
    kept: int
    inserted: int
    updated: int
    duplicates: int
    expired_marked: int
    error: Optional[str] = None


class StatsOut(BaseModel):
    total_jobs: int
    active_jobs: int
    by_category: dict[str, int]
    by_risk_band: dict[str, int]
    last_ingest: Optional[datetime] = None
    model: dict
