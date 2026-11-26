"""Arbeitnow job feed — server-side fetch with an in-memory cache.

No database, no ingestion endpoint, no scheduler. Listings are fetched
from the Arbeitnow free job-board API
(https://www.arbeitnow.com/api/job-board-api, no key required, paginated
with ?page=, 300 jobs per page) on demand and cached in memory for
FEED_CACHE_TTL_SECONDS (default 10 minutes). A refresh is lazy: it
happens on a request whose cache entry has expired, under a lock so
concurrent requests do not stampede the upstream.

Upstream failure:
  * a stale cache exists -> serve it with stale=True, upstream_ok=False
    (HTTP 200);
  * no cache exists -> raise UpstreamUnavailable; the API turns that
    into HTTP 503 with a plain message.

Mapping (preserved from the old backend/ingest.py):
  slug          -> external_id (source "arbeitnow"), id "arbeitnow:<slug>"
  company_name  -> company
  title         -> title
  description   -> description (HTML stripped)
  location      -> location
  url           -> url (original apply link)
  created_at    -> posted_at (unix timestamp)
  job_types     -> category (Werkstudent / Internship / Part-time /
                   Full-time / Other)

Germany focus: keep a listing only if its location is in Germany (or a
German city) or it is remote with no non-German location.

Dedupe: (source, external_id) unique; also normalised
(title, company, location) across the feed.

Listings are NOT scored here: the feed carries no risk information.
Scoring happens only in POST /api/predict, for text the user pastes in.
"""

import json
import os
import re
import ssl
import threading
from datetime import datetime, timezone

import httpx

from .config import (
    ARBEITNOW_API,
    ARBEITNOW_MAX_PAGES,
    FEED_CACHE_TTL_SECONDS,
)

SOURCE = "arbeitnow"
UPSTREAM_UNAVAILABLE_MESSAGE = (
    "Job listings are currently unavailable. Please try again later."
)

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
    "koblenz", "siegen", "hildesheim", "salzgitter",
    "kaiserslautern", "cottbus", "schwerin",
}


class UpstreamUnavailable(Exception):
    """The Arbeitnow API could not be reached and no cache exists."""


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
    """Fetch up to max_pages of raw job dicts. Raises on upstream error."""
    jobs: list[dict] = []
    # ssl.create_default_context() honours SSL_CERT_FILE, so environments
    # whose egress goes through a TLS-intercepting proxy with its own CA
    # (this VM) verify correctly; plain httpx/certifi would reject the
    # proxy's certificate. In production (no SSL_CERT_FILE) the default
    # context uses the system store with the public CAs.
    with httpx.Client(timeout=10, follow_redirects=True, trust_env=False,
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


def normalise_jobs(raw_jobs: list[dict]) -> list[dict]:
    """Filter (Germany focus), dedupe and map raw Arbeitnow rows to the
    public job shape. No risk fields are attached."""
    jobs: list[dict] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str, str]] = set()
    for raw in raw_jobs:
        location = raw.get("location") or ""
        remote = str(raw.get("remote") or "").lower() == "true"
        if not is_german(location, remote):
            continue
        external_id = str(raw.get("slug") or "")
        if not external_id:
            continue
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)
        title = raw.get("title") or ""
        company = raw.get("company_name") or ""
        norm_key = (_norm(title), _norm(company), _norm(location))
        if norm_key in seen_keys:
            continue
        seen_keys.add(norm_key)
        job_types = _as_list(raw.get("job_types"))
        try:
            posted_at = (
                datetime.fromtimestamp(
                    int(raw.get("created_at") or 0), tz=timezone.utc
                )
                if raw.get("created_at") else None
            )
        except (ValueError, TypeError, OSError):
            posted_at = None
        jobs.append({
            "id": f"{SOURCE}:{external_id}",
            "source": SOURCE,
            "external_id": external_id,
            "title": title,
            "company": company,
            "location": location,
            "url": raw.get("url") or "",
            "description": strip_html(raw.get("description") or ""),
            "category": map_category(job_types, title),
            "posted_at": posted_at,
        })
    return jobs


# --- In-memory cache ----------------------------------------------------

_lock = threading.Lock()
_jobs: list[dict] = []
_cached_at: datetime | None = None
_upstream_ok: bool = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cache_age_seconds(now: datetime | None = None) -> int | None:
    if _cached_at is None:
        return None
    return int(((now or _now()) - _cached_at).total_seconds())


def current_status() -> dict:
    """Feed status from the cache alone (no fetch attempt)."""
    now = _now()
    return {
        "source": SOURCE,
        "cached_at": _cached_at,
        "cache_age_seconds": _cache_age_seconds(now),
        "upstream_ok": _upstream_ok,
        "stale": False,
    }


def get_feed() -> dict:
    """Return {"jobs", "cached_at", "stale", "upstream_ok"}.

    Refreshes lazily when the cache is missing or expired, under a lock
    so concurrent requests do not stampede the upstream. On upstream
    failure serves the stale cache when one exists, else raises
    UpstreamUnavailable.
    """
    global _jobs, _cached_at, _upstream_ok
    now = _now()
    with _lock:
        if _cached_at is not None:
            age = (now - _cached_at).total_seconds()
            if age < FEED_CACHE_TTL_SECONDS:
                return {
                    "jobs": list(_jobs),
                    "cached_at": _cached_at,
                    "stale": False,
                    "upstream_ok": _upstream_ok,
                }
        try:
            raw = fetch_arbeitnow()
        except Exception:  # noqa: BLE001 — any upstream failure
            _upstream_ok = False
            if _jobs:
                return {
                    "jobs": list(_jobs),
                    "cached_at": _cached_at,
                    "stale": True,
                    "upstream_ok": False,
                }
            raise UpstreamUnavailable(UPSTREAM_UNAVAILABLE_MESSAGE)
        _jobs = normalise_jobs(raw)
        _cached_at = _now()
        _upstream_ok = True
        return {
            "jobs": list(_jobs),
            "cached_at": _cached_at,
            "stale": False,
            "upstream_ok": True,
        }


def get_job(job_id: str) -> dict | None:
    """One job by its stable string id, or None. Raises
    UpstreamUnavailable when the feed cannot be loaded at all."""
    feed = get_feed()
    for job in feed["jobs"]:
        if job["id"] == job_id:
            return job
    return None


def filter_jobs(
    jobs: list[dict],
    q: str | None = None,
    category: str | None = None,
    sort: str = "newest",
) -> list[dict]:
    """Search / filter / sort in memory.

    q matches title, company or location (case-insensitive substring).
    category is an exact match. sort is newest|oldest by posted_at;
    jobs without a posted_at sort last in both directions.
    """
    result = list(jobs)
    if q:
        needle = q.lower()
        result = [
            j for j in result
            if needle in (j["title"] or "").lower()
            or needle in (j["company"] or "").lower()
            or needle in (j["location"] or "").lower()
        ]
    if category:
        result = [j for j in result if j["category"] == category]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if sort == "oldest":
        result.sort(key=lambda j: j["posted_at"] or epoch)
    else:  # newest
        result.sort(key=lambda j: j["posted_at"] or epoch, reverse=True)
    return result


# --- Test helpers ---------------------------------------------------------

def clear_cache() -> None:
    """Drop the cached feed (tests only)."""
    global _jobs, _cached_at, _upstream_ok
    with _lock:
        _jobs = []
        _cached_at = None
        _upstream_ok = True


def seed_cache(jobs: list[dict], cached_at: datetime | None = None) -> None:
    """Put jobs straight into the cache as if just fetched (tests only)."""
    global _jobs, _cached_at, _upstream_ok
    with _lock:
        _jobs = list(jobs)
        _cached_at = cached_at or _now()
        _upstream_ok = True
