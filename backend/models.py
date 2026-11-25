"""Database models."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from .database import Base


class Job(Base):
    """One job listing, scored by the ML model at ingest time."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_jobs_source_external"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False, index=True)
    external_id = Column(String(255), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    company = Column(String(255), nullable=False, default="")
    location = Column(String(255), nullable=False, default="")
    url = Column(String(1024), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    # Normalised category: Werkstudent | Internship | Part-time | Full-time | Other
    category = Column(String(32), nullable=False, default="Other", index=True)
    employment_type_raw = Column(String(255), nullable=False, default="")
    posted_at = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, nullable=False)
    fraud_probability = Column(Float, nullable=False, default=0.0, index=True)
    risk_band = Column(String(16), nullable=False, default="low", index=True)
    # JSON: {"top_fraud_words": [...], "top_legit_words": [...], "indicators": [...]}
    indicators = Column(Text, nullable=False, default="{}")
    expired = Column(Boolean, nullable=False, default=False, index=True)


class IngestRun(Base):
    """One ingestion run, for the stats endpoint and monitoring."""

    __tablename__ = "ingest_runs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    fetched = Column(Integer, nullable=False, default=0)
    kept = Column(Integer, nullable=False, default=0)
    inserted = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    duplicates = Column(Integer, nullable=False, default=0)
    expired_marked = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
