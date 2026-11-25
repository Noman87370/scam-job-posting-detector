"""Pydantic schemas for the API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    risk_band: str
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


class Indicator(BaseModel):
    code: str
    label: str
    detail: str
    present: bool


class PredictOut(BaseModel):
    fraud_probability: float = Field(ge=0.0, le=1.0)
    risk_band: str
    probability_threshold: float
    top_fraud_words: list[dict[str, Any]] = []
    top_legit_words: list[dict[str, Any]] = []
    indicators: list[Indicator] = []
    disclaimer: str = (
        "This is a risk estimate from a machine-learning model, not a "
        "definitive verdict. Always verify a posting through the employer's "
        "own channels before applying or sharing personal data."
    )


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
