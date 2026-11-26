"""Rule-based German warning-sign checker.

No ML: the rules live in backend/rules_de.py (a plain data file the
user can edit); this module only runs them.

- The text is split into sentences. Each rule regex runs over the
  whole text; the matched sentence is returned as evidence.
  Evidence is raw text — the frontend renders it with React, which
  HTML-escapes it.
- Critical rules are downgraded to "mild" when the matched sentence
  clearly describes a job duty or a legitimate right-to-work check
  at employment start (LEGIT_CONTEXT_MARKERS in rules_de.py).
- Special rule kinds: "messenger_only" (WhatsApp/Telegram/Signal is
  the only contact channel), "no_company" (no company name, address
  or Impressum anywhere), "exclamations" (three or more "!").

Banding (weights: strong = 2, mild = 1; checkboxes count the same):
  any critical -> "high"; 2+ strong, or 1 strong with total weight
  >= 3 -> "some"; otherwise "few", always followed by the line that
  this does not mean the offer is trustworthy. No band ever says the
  offer is "safe" or "not a scam".
"""

import re

from .rules_de import (
    ADVICE_LINK,
    BAND_LABELS,
    CHECKBOXES,
    LEGIT_CONTEXT_MARKERS,
    RULES,
    RULES_VERSION,
)

FEW_NOTE_DE = (
    "Das bedeutet nicht, dass das Angebot seriös ist."
)
FEW_NOTE_EN = "This does not mean the offer is trustworthy."

MAX_EVIDENCE_CHARS = 300

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?\n])\s+")
_OTHER_CHANNEL_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.[a-z]{2,}|www\.|https?://|tel\.?|telefon|\+?\d[\d\s().\-]{7,}\d",
    re.IGNORECASE,
)
_COMPANY_RE = re.compile(
    r"gmbh|aktiengesellschaft|\bug\b|\be\.v\.|impressum"
    r"|stra(?:ß|ss)e|str\.\s*\d|allee|platz\s*\d|weg\s*\d",
    re.IGNORECASE,
)

_COMPILED = [
    (rule, re.compile(rule["pattern"], re.IGNORECASE))
    for rule in RULES
    if rule.get("kind", "regex") == "regex"
]
_BY_ID = {rule["id"]: rule for rule in RULES}
_CHECKBOX_BY_ID = {c["id"]: c for c in CHECKBOXES}


def split_sentences(text: str) -> list[str]:
    """Split into sentences, keeping the punctuation."""
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def _sentence_for(text: str, start: int, end: int) -> str:
    """The sentence containing the match span [start, end)."""
    for sentence in split_sentences(text):
        idx = text.find(sentence)
        if idx != -1 and idx <= start < idx + len(sentence):
            return sentence
    # Fallback: a window around the match.
    lo = max(0, start - 80)
    hi = min(len(text), end + 80)
    return text[lo:hi].strip()


def _evidence(sentence: str) -> str:
    sentence = (sentence or "").strip()
    if len(sentence) > MAX_EVIDENCE_CHARS:
        sentence = sentence[:MAX_EVIDENCE_CHARS].rstrip() + " …"
    return sentence


def _has_legit_context(sentence: str) -> bool:
    low = sentence.lower()
    return any(marker in low for marker in LEGIT_CONTEXT_MARKERS)


def _check_messenger_only(text: str):
    """WhatsApp/Telegram/Signal present, and no other contact channel.

    The messenger mention itself (and the number right after it) is
    stripped first: a WhatsApp number is not a separate contact
    channel, it is the messenger channel.
    """
    m = re.search(r"(whatsapp|telegram|signal)", text, re.IGNORECASE)
    if not m:
        return None
    rest = re.sub(r"(whatsapp|telegram|signal)[^.,\n]{0,60}", "", text, flags=re.IGNORECASE)
    if _OTHER_CHANNEL_RE.search(rest):
        return None
    return _sentence_for(text, m.start(), m.end())


def _check_no_company(text: str):
    if _COMPANY_RE.search(text):
        return None
    sentences = split_sentences(text)
    return sentences[0] if sentences else ""


def _check_exclamations(text: str):
    if text.count("!") < 3:
        return None
    for sentence in split_sentences(text):
        if "!" in sentence:
            return sentence
    return text[:MAX_EVIDENCE_CHARS]


def check_german(text: str, context_flags=None) -> dict:
    """Run the German warning-sign check on raw text.

    context_flags: checkbox ids from CHECKBOXES ("unsolicited",
    "asked_id", "asked_bank_or_fee", "contact_messenger"). Each adds
    its severity to the counts. Returns band, band labels (de/en),
    counts, matched rules with evidence sentences, applied checkboxes,
    and the advice flag for "high" risk.
    """
    text = text or ""
    context_flags = list(context_flags or [])
    matched = []
    seen_rules = set()

    def _add(rule, severity, evidence, downgraded=False):
        if rule["id"] in seen_rules:
            return
        seen_rules.add(rule["id"])
        matched.append({
            "rule_id": rule["id"],
            "category": rule["category"],
            "severity": severity,
            "explanation_de": rule["explanation_de"],
            "explanation_en": rule["explanation_en"],
            "evidence": _evidence(evidence),
            "downgraded": downgraded,
        })

    for rule, pattern in _COMPILED:
        m = pattern.search(text)
        if not m:
            continue
        sentence = _sentence_for(text, m.start(), m.end())
        severity = rule["severity"]
        downgraded = False
        if severity == "critical" and _has_legit_context(sentence):
            severity = "mild"
            downgraded = True
        _add(rule, severity, sentence, downgraded)

    for rule in RULES:
        kind = rule.get("kind", "regex")
        if kind == "messenger_only":
            sentence = _check_messenger_only(text)
            if sentence is not None:
                _add(rule, rule["severity"], sentence)
        elif kind == "no_company":
            sentence = _check_no_company(text)
            if sentence is not None:
                _add(rule, rule["severity"], sentence)
        elif kind == "exclamations":
            sentence = _check_exclamations(text)
            if sentence is not None:
                _add(rule, rule["severity"], sentence)

    # User-reported context (checkboxes) counts like a matched rule.
    checkboxes_applied = []
    for flag in context_flags:
        checkbox = _CHECKBOX_BY_ID.get(flag)
        if not checkbox:
            continue
        checkboxes_applied.append({
            "id": checkbox["id"],
            "severity": checkbox["severity"],
            "text_de": checkbox["text_de"],
            "text_en": checkbox["text_en"],
        })

    def _count(items, severity):
        return sum(1 for x in items if x["severity"] == severity)

    critical = _count(matched, "critical") + _count(checkboxes_applied, "critical")
    strong = _count(matched, "strong") + _count(checkboxes_applied, "strong")
    mild = _count(matched, "mild") + _count(checkboxes_applied, "mild")

    if critical >= 1:
        band = "high"
    elif strong >= 2 or (strong >= 1 and 2 * strong + mild >= 3):
        band = "some"
    else:
        band = "few"

    label_de, label_en = BAND_LABELS[band]
    return {
        "band": band,
        "band_label_de": label_de,
        "band_label_en": label_en,
        "rules_version": RULES_VERSION,
        "critical": critical,
        "strong": strong,
        "mild": mild,
        "matched": matched,
        "checkboxes_applied": checkboxes_applied,
        "advice": band == "high",
        "advice_link": ADVICE_LINK,
        "few_note_de": FEW_NOTE_DE if band == "few" else "",
        "few_note_en": FEW_NOTE_EN if band == "few" else "",
    }
