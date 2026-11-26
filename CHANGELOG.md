# Changelog

## 2026-11-26 — Final fix-and-polish round (Option S)

- Removed the database, the ingestion endpoint, the in-process scheduler and the GitHub Actions ingest cron. The backend now fetches Arbeitnow listings server-side on demand, with an in-memory cache (10-minute TTL, 10 s timeout, at most 3 pages).
- Removed risk labels from feed listings. Scoring happens only for text the user pastes, via `POST /api/predict`.
- Rewrote the README, `ARCHITECTURE.md`, `DEPLOYMENT.md` and `model/METRICS.md` for the no-database design; added the MIT `LICENSE` and a CI workflow (`.github/workflows/ci.yml`) that runs pytest on every push and pull request.

## 2026-11-26 — Code-quality review (commit 2fb15a4)

- Reviewed the codebase after the `de_id_check` fix; no functional change to the checker or the model.
- Pushed as commit 2fb15a4 and verified live: the frontend bundle hash changed, `/health` reported the model loaded, an English scam-like test returned the ML path with "High risk", and the Enpal test returned "Few warning signs" with `de_id_check` silent.

## 2026-11-26 — German identity-check rule fix

- The identity-check rule (`de_id_check`) matched the bare verb stem "identifizier*" / "identifik*", which flagged ordinary duty wording ("Du identifizierst Wachstumspotenziale", "Identifikation von Engpässen") — all 58 High-risk feed rows carried that one rule.
- The rule now matches only the noun "Identitätsprüfung". Real scam wording is still covered by the Video-Ident and ID-copy rules. The three wrongly flagged sentences are regression tests in `tests/test_de_rules.py`.
- The rule set had a version (`RULES_VERSION` in `backend/rules_de.py`, `2026-11-26-v2`), stored with every German feed row; when a rule changed, the next ingest re-scored stored German rows whose stored version differed, so a fix healed the feed instead of leaving old rows wrong. (That stored-row mechanism no longer exists: the 2026-11-26 final round below removed the database and the feed is no longer scored.)
- The stored feed was rescored the same evening: High-risk rows went from 71 to 0, with 8 rows at "Some warning signs" and 929 at "Few warning signs" (938 total, 937 active).

## 2026-11-25 — Round 2: bilingual checker (German + English)

- Added the German rule-based warning-sign checker (rules in a data file, context downgrade for legitimate cases, checkboxes, advice box with a Verbraucherzentrale link) and a DE/EN UI toggle with all text in one translations file (`i18n.js`).
- Added a posting-language selector (Auto / Deutsch / English) with mixed-language and unsupported-language handling; feed rows are scored by language.
- Verified the English pipeline is identical to the notebook. 49/49 tests pass. Pushed as commit f7aacab and verified live.

## 2026-11-25 — Round 1: English checker live

- Shipped the English-only checker: score-based bands (High risk / Some warning signs / Few warning signs), a structured form, anonymised URL/email/phone placeholders, pasted text not stored, and the model as the committed `model_artifacts.joblib` (no retrain at build), with scikit-learn pinned to 1.9.1.
- 24/24 tests pass. Pushed as commit 7a2d2c3; the live application was verified working the same evening.
