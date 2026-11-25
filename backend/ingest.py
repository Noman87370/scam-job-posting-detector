"""Ingestion from the Arbeitnow free job-board API.

API: https://www.arbeitnow.com/api/job-board-api (no key required,
paginated with ?page=, 300 jobs per page, updated hourly).

Mapping:
  slug          -> external_id (source "arbeitnow")
  company_name  -> company
  title         -> title
  description   -> description (HTML stripped for scoring; raw kept)
  location      -> location
  url           -> url (original apply link)
  created_at    -> posted_at (unix timestamp)
  job_types     -> category (Werkstudent / Internship / Part-time /
                   Full-time / Other)
  remote        -> telecommuting flag for the model

Germany focus: keep a listing only if its location is in Germany (or a
German city) or it is remote with no non-German location.

Metadata flags for the model are computed from the raw text with regex
(URL/email/phone present, missing profile/requirements, salary present,
text length) because Kaggle's anonymised #URL_/#EMAIL_/#PHONE_ tokens do
not exist in live data — see common.features.

Dedupe: (source, external_id) unique; also normalised
(title, company, location) across sources.

Expiry: a posting is marked expired when posted_at is older than 60 days,
or when a full ingest no longer lists it and it is older than 7 days.
Listings are never deleted.
"""

import json
import os
import re
import ssl
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from .config import ARBEITNOW_API, ARBEITNOW_MAX_PAGES
from .database import SessionLocal
from .ml import predict
from .models import IngestRun, Job

SOURCE = "arbeitnow"
EXPIRY_DAYS = 60
NOT_SEEN_EXPIRY_DAYS = 7

GERMAN_CITIES = {
    "berlin", "munich", "münchen", "hamburg", "cologne", "köln", "frankfurt",
    "stuttgart", "düsseldorf", "dortmund", "essen", "leipzig", "bremen",
    "dresden", "hanover", "hannover", "nuremberg", "nürnberg", "duisburg",
    "bochum", "wuppertal", "bielefeld", "bonn", "münster", "karlsruhe",
    "mannheim", "augsburg", "wiesbaden", "gelsenkirchen", "mönchengladbach",
    "braunschweig", "chemnitz", "kiel", "aachen", "halle", "magdeburg",
    "freiburg", "krefeld", "lübeck", "oberhausen", "erfurt", "mainz",
    "rostock", "kassel", "hagen", "hamm", "saarbrücken", "mülheim",
    "potsdam", "ludwigshafen", "oldenburg", "leverkusen", "osnabrück",
    "solingen", "heidelberg", "herne", "neuss", "darmstadt", "paderborn",
    "regensburg", "ingolstadt", "würzburg", "fürth", "wolfsburg", "ulm",
    "heilbronn", "pforzheim", "göttingen", "bottrop", "trier",
    "recklinghausen", "bremerhaven", "jena", "remscheid", "erlangen",
    "freiburg", "ulm", "koblenz", "siegen", "hildesheim", "salzgitter",
    "kaiserslautern", "cottbus", "schwerin",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower())).strip()


def is_german(location: str, remote: bool) -> bool:
    loc = (location or "").strip().lower()
    if "germany" in loc or "deutschland" in loc:
        return True
    cities = {c for c in GERMAN_CITIES if c in loc}
    if cities:
        return True
    if remote and not loc:
        return True  # remote with no location stated: keep, user can filter
    return False


def _as_list(value):
    """Arbeitnow returns tags/job_types as lists or JSON-encoded strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except (ValueError, TypeError):
            pass
        return [s]
    return [str(value)]


def map_category(job_types, title: str) -> str:
    text = " ".join(job_types + [title or ""]).lower()
    if "werkstudent" in text or "working student" in text:
        return "Werkstudent"
    if "internship" in text or "intern" in text or "praktikum" in text:
        return "Internship"
    if "teilzeit" in text or "part-time" in text or "part time" in text:
        return "Part-time"
    if ("vollzeit" in text or "full-time" in text or "full time" in text
            or "fulltime" in text):
        return "Full-time"
    return "Other"


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _proxy():
    """Proxy URL from the environment, if one is configured.

    httpx's own environment-proxy parsing cannot handle bracketed IPv6
    entries in no_proxy (e.g. "[::1]" raises InvalidURL "Invalid port:
    ':1]'"), so we read the proxy URL explicitly and disable trust_env.
    Without a proxy configured (production), this returns None and the
    client connects directly.
    """
    return (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
            or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"))


def fetch_arbeitnow(max_pages: int = ARBEITNOW_MAX_PAGES) -> list[dict]:
    """Fetch all pages. Returns raw job dicts."""
    jobs: list[dict] = []
    # ssl.create_default_context() honours SSL_CERT_FILE, so environments
    # whose egress goes through a TLS-intercepting proxy with its own CA
    # (this VM) verify correctly; plain httpx/certifi would reject the
    # proxy's certificate. In production (no SSL_CERT_FILE) the default
    # context uses the system store with the public CAs.
    with httpx.Client(timeout=30, follow_redirects=True, trust_env=False,
                      proxy=_proxy(), verify=ssl.create_default_context(),
                      headers={"Accept": "application/json",
                               "User-Agent": "scam-job-detector/1.0"}) as client:
        for page in range(1, max_pages + 1):
            resp = client.get(ARBEITNOW_API, params={"page": page})
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if not data:
                break
            jobs.extend(data)
            if len(data) < 300:
                break
    return jobs


def ingest_arbeitnow(db: Session | None = None) -> dict:
    """Fetch, filter, score and store. Returns counts.

    Datetimes are stored as naive UTC (SQLite stores datetimes as plain
    strings, so tz-aware and naive values must not be mixed).
    """
    own_session = db is None
    db = db or SessionLocal()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run = IngestRun(source=SOURCE, started_at=now)
    db.add(run)
    db.commit()
    counts = {"fetched": 0, "kept": 0, "inserted": 0, "updated": 0,
              "duplicates": 0, "expired_marked": 0}
    # Normalised keys of all active jobs, for the cross-source dup check.
    existing_keys = {
        (_norm(j.title), _norm(j.company), _norm(j.location))
        for j in db.query(Job).filter(Job.expired.is_(False)).all()
    }
    try:
        raw_jobs = fetch_arbeitnow()
        counts["fetched"] = len(raw_jobs)
        seen_ids: set[str] = set()
        for raw in raw_jobs:
            location = raw.get("location") or ""
            remote = str(raw.get("remote") or "").lower() == "true"
            if not is_german(location, remote):
                continue
            counts["kept"] += 1
            external_id = str(raw.get("slug") or "")
            if not external_id:
                continue
            if external_id in seen_ids:
                # Same posting twice in one feed: a duplicate, not an update.
                counts["duplicates"] += 1
                continue
            seen_ids.add(external_id)
            title = raw.get("title") or ""
            company = raw.get("company_name") or ""
            description = strip_html(raw.get("description") or "")
            job_types = _as_list(raw.get("job_types"))
            category = map_category(job_types, title)
            try:
                posted_at = datetime.fromtimestamp(
                    int(raw.get("created_at") or 0), tz=timezone.utc
                ).replace(tzinfo=None) if raw.get("created_at") else None
            except (ValueError, TypeError, OSError):
                posted_at = None
            fields = {
                "title": title,
                "company_profile": "",
                "description": description,
                "requirements": "",
                "benefits": "",
                "company": company,
                "salary_range": "",
                "telecommuting": remote,
                "has_company_logo": False,
                "has_questions": False,
            }
            score = predict(fields)
            indicators_json = json.dumps({
                "top_fraud_words": score["top_fraud_words"],
                "top_legit_words": score["top_legit_words"],
                "indicators": score["indicators"],
            })
            existing = db.query(Job).filter(
                Job.source == SOURCE, Job.external_id == external_id
            ).first()
            if existing:
                existing.title = title
                existing.company = company
                existing.location = location
                existing.url = raw.get("url") or existing.url
                existing.description = description
                existing.category = category
                existing.employment_type_raw = ", ".join(job_types)
                existing.posted_at = posted_at
                existing.fetched_at = now
                existing.fraud_probability = score["fraud_probability"]
                existing.risk_band = score["risk_band"]
                existing.indicators = indicators_json
                existing.expired = False
                counts["updated"] += 1
                continue
            # Cross-source duplicate check on normalised title/company/location.
            norm_key = (_norm(title), _norm(company), _norm(location))
            if norm_key in existing_keys:
                counts["duplicates"] += 1
                continue
            existing_keys.add(norm_key)
            db.add(Job(
                source=SOURCE, external_id=external_id, title=title,
                company=company, location=location,
                url=raw.get("url") or "", description=description,
                category=category, employment_type_raw=", ".join(job_types),
                posted_at=posted_at, fetched_at=now,
                fraud_probability=score["fraud_probability"],
                risk_band=score["risk_band"], indicators=indicators_json,
                expired=False,
            ))
            counts["inserted"] += 1
        db.commit()

        # Expiry pass.
        cutoff = now - timedelta(days=EXPIRY_DAYS)
        old = db.query(Job).filter(
            Job.expired.is_(False), Job.posted_at.isnot(None),
            Job.posted_at < cutoff,
        ).all()
        for job in old:
            job.expired = True
            counts["expired_marked"] += 1
        not_seen_cutoff = now - timedelta(days=NOT_SEEN_EXPIRY_DAYS)
        stale = db.query(Job).filter(
            Job.source == SOURCE, Job.expired.is_(False),
            Job.posted_at.isnot(None), Job.posted_at < not_seen_cutoff,
        ).all()
        for job in stale:
            if job.external_id not in seen_ids:
                job.expired = True
                counts["expired_marked"] += 1
        db.commit()
    except Exception as exc:  # noqa: BLE001 — recorded on the run, never crashes the app
        db.rollback()
        run.error = str(exc)
        counts["error"] = str(exc)
    finally:
        run.fetched = counts["fetched"]
        run.kept = counts["kept"]
        run.inserted = counts["inserted"]
        run.updated = counts["updated"]
        run.duplicates = counts["duplicates"]
        run.expired_marked = counts["expired_marked"]
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        if own_session:
            db.close()
    return {"source": SOURCE, **counts}
