"""Pydantic schemas for the API.

The checker returns a decision score and a risk band — never a
probability presented as a "% chance of scam". The fraud probability
is kept on stored jobs only, for sorting; it is not part of the
checker response.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER = (
    "This is a statistical estimate, not proof. The model misses about "
    "1 in 4 scams and can flag real postings."
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


class Indicator(BaseModel):
    code: str
    label: str
    detail: str
    present: bool


class Contribution(BaseModel):
    feature: str
    contribution: float


class PredictOut(BaseModel):
    decision_score: float
    risk_band: str  # high | some | few
    risk_label: str  # "High risk" | "Some warning signs" | "Few warning signs"
    threshold: float  # decision-function score for "high risk" (0.949)
    top_raising: list[Contribution] = []
    top_lowering: list[Contribution] = []
    indicators: list[Indicator] = []
    language: Optional[str] = None
    language_ok: bool = True
    language_message: str = ""
    disclaimer: str = DISCLAIMER


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
    by_category: dict
    by_risk_band: dict
    last_ingest: Optional[datetime] = None
    model: dict
