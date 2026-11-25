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

Metadata flags for the model are computed from the text exactly as in
training (see common.features): real URLs, emails and phone numbers
are first converted to the Kaggle-style placeholders, then the flags
are placeholder presence. The Arbeitnow API does not return a company
profile or requirements, so no_profile / no_requirements are 1 for
every ingested listing — the model sees those listings as thinner
than a full posting.

Language: the model was trained on English only. Each listing's
language is detected at ingest and stored. English listings are scored
by the ML model; German listings are checked with the rule-based
warning-sign checker (backend/de_rules.py) instead — the English model
cannot judge German text. The dashboard shows a risk band only for
English and German listings. Rows ingested before the language column
existed are backfilled on the next ingest run.

Dedupe: (source, external_id) unique; also normalised
(title, company, location) across sources.

Expiry: a posting is marked expired when posted_at is older than 60 days,
or when a full ingest no longer lists it and it is older than 7 days.
Listings are never deleted.
"""

import json
import math
import os
import re
import ssl
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from .config import ARBEITNOW_API, ARBEITNOW_MAX_PAGES
from .database import SessionLocal
from .de_rules import check_german
from .language import detect_language
from .ml import predict, risk_band
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


def _score_listing(fields: dict, title: str, description: str) -> dict:
    """Score one listing for the feed, by language.

    English -> the ML model (as before). German -> the rule-based
    warning-sign checker (no ML score exists for German, so
    fraud_probability is 0.0 and decision_score is None; the band
    comes from the rules). Other languages -> the ML score as before,
    but the dashboard hides the band ("Not scored"). A failure in one
    row never stops the ingest run: the row is stored unscored.
    """
    text = f"{title or ''} {description or ''}"
    lang = detect_language(text)
    try:
        if lang == "de":
            result = check_german(text)
            return {
                "fraud_probability": 0.0,
                "decision_score": None,
                "risk_band": result["band"],
                "language": "de",
                "indicators": json.dumps({
                    "method": "de",
                    "matched": result["matched"],
                    "critical": result["critical"],
                    "strong": result["strong"],
                    "mild": result["mild"],
                }),
            }
        score = predict(fields)
        return {
            "fraud_probability": score["fraud_probability"],
            "decision_score": score["decision_score"],
            "risk_band": score["risk_band"],
            "language": score["language"],
            "indicators": json.dumps({
                "method": "ml",
                "top_raising": score["top_raising"],
                "top_lowering": score["top_lowering"],
                "indicators": score["indicators"],
            }),
        }
    except Exception:  # noqa: BLE001 — one bad row must not stop ingestion
        return {
            "fraud_probability": 0.0,
            "decision_score": None,
            "risk_band": "few",
            "language": lang,
            "indicators": json.dumps({"method": "unscored"}),
        }


def _backfill_scores(db: Session) -> int:
    """Fill language / decision_score / risk_band on older rows.

    English rows ingested before those columns existed get their
    decision score recovered exactly from the stored probability (for
    logistic regression, score = log(p / (1 - p))), and the band
    follows from the score. German rows get the rule-based check
    instead — their stored ML score was computed on German text, which
    the English-only model cannot judge. Rows already carrying a "de"
    method marker are skipped. Runs once per row — later runs find
    nothing to do.
    """
    rows = db.query(Job).all()
    updated = 0
    for job in rows:
        try:
            indicators = json.loads(job.indicators or "{}")
        except (ValueError, TypeError):
            indicators = {}
        try:
            if job.language is None:
                job.language = detect_language(
                    f"{job.title or ''} {job.description or ''}"
                )
            if job.language == "de" and indicators.get("method") != "de":
                result = check_german(
                    f"{job.title or ''} {job.description or ''}"
                )
                job.fraud_probability = 0.0
                job.decision_score = None
                job.risk_band = result["band"]
                job.indicators = json.dumps({
                    "method": "de",
                    "matched": result["matched"],
                    "critical": result["critical"],
                    "strong": result["strong"],
                    "mild": result["mild"],
                })
                updated += 1
            elif job.decision_score is None and job.language == "en":
                p = min(max(float(job.fraud_probability or 0.0), 1e-6), 1 - 1e-6)
                job.decision_score = round(math.log(p / (1 - p)), 4)
                job.risk_band = risk_band(job.decision_score)
                updated += 1
        except Exception:  # noqa: BLE001 — one bad row must not stop the pass
            continue
    if updated:
        db.commit()
    return updated


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
    # Backfill older rows (language / decision_score) before fetching.
    try:
        _backfill_scores(db)
    except Exception:  # noqa: BLE001 — backfill must never block ingestion
        db.rollback()
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
            score = _score_listing(fields, title, description)
            indicators_json = score["indicators"]
            job_language = score["language"]
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
                existing.decision_score = score["decision_score"]
                existing.risk_band = score["risk_band"]
                existing.language = job_language
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
                decision_score=score["decision_score"],
                risk_band=score["risk_band"], language=job_language,
                indicators=indicators_json,
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
