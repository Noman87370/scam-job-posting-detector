"""Configuration — everything comes from environment variables.

There is no database: the job feed is fetched server-side from the
Arbeitnow API on demand and held in an in-memory cache (see
backend/feed.py). No secrets are ever committed; see .env.example.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(ROOT_DIR, "model"))
FRONTEND_DIR = os.environ.get(
    "FRONTEND_DIR", os.path.join(BASE_DIR, "static")
)
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
# At most this many Arbeitnow pages (300 jobs each) per upstream fetch.
ARBEITNOW_MAX_PAGES = int(os.environ.get("ARBEITNOW_MAX_PAGES", "3"))
# In-memory feed cache lifetime, in seconds (default 10 minutes).
FEED_CACHE_TTL_SECONDS = int(os.environ.get("FEED_CACHE_TTL_SECONDS", "600"))
