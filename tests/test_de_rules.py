"""German rule checker: synthetic sanity check (NOT a validation).

Reads tests/de_cases.csv — 20 fictional scam-like German texts and 20
realistic legitimate German texts (no real company names). The script
prints the share of scam-like texts flagged (band "high" or "some"),
the false-alarm rate on legitimate texts, and lists every miss.

This is a small synthetic sanity check only: the texts are invented by
the author, the rules were written with these cases in mind, and the
German check has no labelled validation data. It shows the rules work
as intended on these examples — nothing more.

Run with: pytest tests/test_de_rules.py -s   (or: python tests/test_de_rules.py)
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.de_rules import check_german  # noqa: E402
from backend.language import analyze_language  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "de_cases.csv")


def load_cases():
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run_sanity_check(verbose=True):
    """Run the checker over the CSV. Returns (scam_flagged, legit_false)."""
    cases = load_cases()
    scam = [c for c in cases if c["label"] == "scam"]
    legit = [c for c in cases if c["label"] == "legit"]
    assert len(scam) == 20, f"expected 20 scam cases, got {len(scam)}"
    assert len(legit) == 20, f"expected 20 legit cases, got {len(legit)}"

    scam_flagged = []
    scam_missed = []
    for case in scam:
        result = check_german(case["text"])
        if result["band"] in ("high", "some"):
            scam_flagged.append(case["id"])
        else:
            scam_missed.append((case["id"], result["band"]))

    legit_false = []
    legit_ok = []
    for case in legit:
        result = check_german(case["text"])
        if result["band"] in ("high", "some"):
            legit_false.append((case["id"], result["band"],
                                [m["rule_id"] for m in result["matched"]]))
        else:
            legit_ok.append(case["id"])

    if verbose:
        print(f"\nGerman rule check — synthetic sanity check ({CSV_PATH})")
        print(f"Scam-like flagged (high/some): {len(scam_flagged)}/20 "
              f"= {len(scam_flagged) / 20:.0%}")
        print(f"Legitimate false alarms (high/some): {len(legit_false)}/20 "
              f"= {len(legit_false) / 20:.0%}")
        if scam_missed:
            print("Scam-like texts NOT flagged (misses):")
            for case_id, band in scam_missed:
                print(f"  - {case_id}: band={band}")
        if legit_false:
            print("Legitimate texts flagged (false alarms):")
            for case_id, band, rules in legit_false:
                print(f"  - {case_id}: band={band}, rules={rules}")
    return scam_flagged, legit_false


def test_german_sanity_check(capsys):
    scam_flagged, legit_false = run_sanity_check(verbose=True)
    # Honest bars for this small synthetic set: at least 17 of 20
    # scam-like texts flagged, at most 3 of 20 legitimate texts
    # flagged. The printed shares and miss lists are the real result.
    assert len(scam_flagged) >= 17, f"only {len(scam_flagged)}/20 scam texts flagged"
    assert len(legit_false) <= 3, f"{len(legit_false)}/20 legit texts flagged"


def test_critical_rules_fire_on_scam_texts():
    cases = {c["id"]: c for c in load_cases()}
    for case_id in ("S01_video_ident", "S02_bank_tester", "S03_finanzagent",
                    "S04_paketagent", "S05_pay_first", "S06_tax_pin",
                    "S07_passport_selfie", "S08_crypto", "S14_video_pay",
                    "S15_forward", "S16_fees", "S17_identity", "S18_bank_test2"):
        result = check_german(cases[case_id]["text"])
        assert result["band"] == "high", f"{case_id}: expected high, got {result['band']}"
        assert result["critical"] >= 1
        assert result["advice"] is True


def test_strong_only_texts_are_some_not_high():
    cases = {c["id"]: c for c in load_cases()}
    for case_id in ("S09_easy_money", "S10_task_scam", "S11_messenger_instant",
                    "S12_orders", "S13_high_pay", "S20_strong_mild"):
        result = check_german(cases[case_id]["text"])
        assert result["band"] == "some", f"{case_id}: expected some, got {result['band']}"
        assert result["critical"] == 0


def test_mild_only_text_is_few():
    # S19 has only mild signals (exclamation marks, free mail, no
    # company details). It is scam-like but the rules deliberately do
    # not call it "some" — mild signals alone are not enough.
    cases = {c["id"]: c for c in load_cases()}
    result = check_german(cases["S19_mild_only"]["text"])
    assert result["band"] == "few"
    assert result["critical"] == 0 and result["strong"] == 0
    assert result["mild"] >= 1
    assert result["few_note_de"] and result["few_note_en"]


def test_tricky_legit_cases_are_not_critical():
    """Bank advisor duties, work-permit ID checks and a fintech
    product description must not fire a critical rule."""
    cases = {c["id"]: c for c in load_cases()}
    for case_id in ("L01_bank_advisor", "L02_work_permit",
                    "L17_online_banking_product", "L18_fintech_product"):
        result = check_german(cases[case_id]["text"])
        assert result["critical"] == 0, (
            f"{case_id}: critical rules fired: "
            f"{[m['rule_id'] for m in result['matched'] if m['severity'] == 'critical']}"
        )
        assert result["band"] == "few", f"{case_id}: expected few, got {result['band']}"


def test_legit_cases_with_single_strong_are_few():
    # One strong signal alone (e.g. "keine Erfahrung nötig") is not
    # enough for "some" — unless a mild signal joins it: 1 strong
    # (weight 2) + 1 mild (weight 1) = 3, which the banding counts as
    # "some". L09 is that case (home-office ad with no company details
    # given): it lands on "some" and is counted as a false alarm in
    # the sanity check, with the fired rules shown to the user.
    cases = {c["id"]: c for c in load_cases()}
    result = check_german(cases["L08_no_experience"]["text"])
    assert result["band"] == "few", f"L08: expected few, got {result['band']}"
    assert result["strong"] == 1 and result["mild"] == 0
    result = check_german(cases["L09_homeoffice"]["text"])
    assert result["band"] == "some", f"L09: expected some, got {result['band']}"
    assert result["strong"] == 1 and result["mild"] == 1


def test_checkboxes_change_the_band():
    base = (
        "Wir suchen eine Aushilfe für unser Lager in Nürnberg, 12 Stunden "
        "pro Woche, 15 Euro pro Stunde. Sie sortieren Waren und bereiten "
        "Sendungen vor. Bewerbung an bewerbung@lager-beispiel.de. "
        "Logistik Beispiel GmbH, Hafenstraße 2, 90768 Fürth."
    )
    assert check_german(base)["band"] == "few"
    # Unsolicited offer alone: one strong -> still "few".
    assert check_german(base, ["unsolicited"])["band"] == "few"
    # Asked for ID before a contract: critical -> "high".
    result = check_german(base, ["asked_id"])
    assert result["band"] == "high"
    assert result["critical"] == 1
    assert result["advice"] is True
    assert [c["id"] for c in result["checkboxes_applied"]] == ["asked_id"]
    # Asked to open a bank account or pay a fee: critical -> "high".
    assert check_german(base, ["asked_bank_or_fee"])["band"] == "high"
    # Unsolicited + messenger-only: two strong -> "some".
    result = check_german(base, ["unsolicited", "contact_messenger"])
    assert result["band"] == "some"
    assert result["strong"] == 2
    # Unknown checkbox ids are ignored.
    assert check_german(base, ["not_a_flag"])["band"] == "few"


def test_banding_boundaries():
    # 1 strong + 1 mild = weight 3 -> "some".
    text = (
        "Ohne Erfahrung können Sie bei uns arbeiten. Schreiben Sie uns an "
        "bewerbung-team@gmail.com. Wir freuen uns auf Ihre Nachricht und "
        "bieten flexible Arbeitszeiten in einem netten Team in Nürnberg."
    )
    result = check_german(text)
    assert result["strong"] == 1 and result["mild"] >= 1
    assert result["band"] == "some"
    # 3 mild alone -> "few" (no strong signal).
    text_mild = (
        "Wir suchen Mitarbeiter für einfache Aufgaben!!! Tolle "
        "Verdienstmöglichkeiten, flexible Arbeitszeiten! Schreiben Sie uns "
        "an job-leicht@gmail.com. Wir sind ein junges Team und freuen uns "
        "auf Ihre Nachricht!"
    )
    result = check_german(text_mild)
    assert result["strong"] == 0 and result["mild"] >= 3
    assert result["band"] == "few"


def test_evidence_is_the_matched_sentence():
    text = (
        "Wir suchen Mitarbeiter für leichte Heimarbeit. Bitte senden Sie uns "
        "ein Foto Ihres Personalausweises, Vorder- und Rückseite, und machen "
        "Sie ein Video-Ident zur Identitätsprüfung. Die Stelle ist in "
        "Teilzeit, 20 Stunden pro Woche, in Nürnberg."
    )
    result = check_german(text)
    video = [m for m in result["matched"] if m["rule_id"] == "de_id_video"]
    assert len(video) == 1
    assert "Video-Ident" in video[0]["evidence"]
    assert "Personalausweis" in video[0]["evidence"] or "Identitätsprüfung" in video[0]["evidence"]
    # Every match carries an explanation in both languages.
    for m in result["matched"]:
        assert m["explanation_de"] and m["explanation_en"]


def test_language_routing():
    de = (
        "Als Werkstudentin oder Werkstudent unterstützen Sie unser Team in "
        "Erlangen bei der Datenanalyse mit SQL und Python. Für die "
        "Arbeitserlaubnis benötigen wir eine Kopie Ihres Reisepasses und "
        "Ihren Aufenthaltstitel. Die Stelle umfasst 15 Stunden pro Woche."
    )
    en = (
        "As a working student in our Data Analytics team in Erlangen you "
        "will support data collection, validation and reporting with SQL "
        "and Power BI. You will document your results, present them to the "
        "team in our weekly meeting, and help maintain our dashboards."
    )
    fr = (
        "Nous recherchons un étudiant en alternance pour notre équipe à "
        "Erlangen. Vous participerez à la collecte de données et à la "
        "préparation de rapports avec SQL et Power BI. Le poste est à temps "
        "partiel, 15 heures par semaine, avec des horaires flexibles."
    )
    mixed = (
        "Wir suchen Mitarbeiter für leichte Heimarbeit von zu Hause aus. Sie "
        "verdienen 500 Euro pro Tag ohne Erfahrung. We are looking for "
        "employees for easy home office work. You earn 500 euros per day "
        "with no experience needed. Sofortige Zusage ohne "
        "Vorstellungsgespräch. Immediate acceptance with no interview "
        "required. Tägliche Auszahlung. Daily payout."
    )
    assert analyze_language(de)["code"] == "de"
    assert analyze_language(en)["code"] == "en"
    assert analyze_language(fr)["code"] == "fr"
    result = analyze_language(mixed)
    assert result["mixed"] is True
    # Detection only runs on text of at least 100 characters.
    assert analyze_language("Kurzer Text.")["unsure"] is True
    assert analyze_language("Kurzer Text.")["code"] is None


def test_html_in_input_is_returned_verbatim_for_the_frontend_to_escape():
    # The backend must not strip or interpret HTML in pasted text: it
    # returns the matched sentence verbatim (JSON-encoded), and the
    # frontend renders it as text (React escapes it). If the backend
    # stripped the markup, the evidence would lose the attack string.
    text = (
        "Bitte machen Sie ein Video-Ident zur Identifizierung. "
        "<script>alert(1)</script> Senden Sie uns außerdem ein Foto Ihres "
        "Personalausweises zur Prüfung. Die Stelle ist in Teilzeit, 20 "
        "Stunden pro Woche, in Nürnberg, und wir freuen uns auf Sie."
    )
    result = check_german(text)
    assert result["band"] == "high"
    evidence = " ".join(m["evidence"] for m in result["matched"])
    assert "<script>alert(1)</script>" in evidence


def test_frontend_never_injects_html():
    # The frontend renders evidence and user text with React text
    # interpolation only — there must be no dangerouslySetInnerHTML or
    # innerHTML anywhere in the bundle source.
    app_jsx = os.path.join(HERE, "..", "frontend", "src", "App.jsx")
    with open(app_jsx, encoding="utf-8") as f:
        source = f.read()
    assert "dangerouslySetInnerHTML" not in source
    assert "innerHTML" not in source


if __name__ == "__main__":
    run_sanity_check(verbose=True)
