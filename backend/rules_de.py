"""German warning-sign rules (data file — edit freely, no code logic here).

Each rule has: id, category, severity ("critical" / "strong" / "mild"),
a case-insensitive regex, and a plain-language explanation in German
and in English. The checker (backend/de_rules.py) runs these patterns
against the pasted text and shows the matched sentence as evidence.

Umlaut handling: patterns use alternations so both spellings match,
e.g. (?:ae|ä) for ä/ae, (?:oe|ö) for ö/oe, (?:ue|ü) for ü/ue,
(?:ss|ß) for ss/ß. Variants like Video-Ident / Videoident / Video Ident
are covered with [-\\s]? between the parts.

Severity meanings (see de_rules.py for the banding):
  critical — any one of these means "High risk", unless the matched
             sentence is clearly a job duty or a right-to-work check
             (see LEGIT_CONTEXT_MARKERS), in which case it is
             downgraded to "mild".
  strong   — weight 2 in the banding.
  mild     — weight 1 in the banding.

Special rule kinds (handled by the checker, not by a plain regex):
  "messenger_only" — fires only when WhatsApp/Telegram/Signal is the
                     ONLY contact channel (no email, phone or website).
  "no_company"     — fires when no company name, address or Impressum
                     is mentioned at all.
  "exclamations"   — fires when the text has three or more "!".
"""

ADVICE_LINK = (
    "https://www.verbraucherzentrale.de/wissen/digitale-welt/datenschutz/"
    "gefaelschte-stellenanzeigen-was-ist-jobscamming-28475"
)

# Version of this rule set. Bump it whenever a rule changes. The ingest
# backfill (backend/ingest.py) re-scores stored German rows whose stored
# rules_version differs from this one, so a rule fix heals the live
# feed on the next ingest instead of leaving old rows wrong.
RULES_VERSION = "2026-11-26-v2"

# Phrases in the matched sentence that show the text is a job duty or a
# legitimate right-to-work check at employment start — not a demand on
# the applicant. A critical rule whose matched sentence contains one of
# these is downgraded to "mild" instead of firing as critical.
LEGIT_CONTEXT_MARKERS = [
    "arbeitserlaubnis",
    "aufenthaltstitel",
    "aufenthaltsgenehmigung",
    "visum",
    "vertragsbeginn",
    "arbeitsbeginn",
    "beschäftigungsbeginn",
    "beschaeftigungsbeginn",
    "ersten arbeitstag",
    "ihre aufgaben",
    "aufgaben:",
    "zu ihren aufgaben",
    "ihr aufgabengebiet",
    "für unsere kunden",
    "fuer unsere kunden",
    "unsere kunden",
    "kunden nutzen",
    "für kunden",
    "fuer kunden",
    "sie beraten",
    "sie betreuen",
    "sie unterstützen",
    "sie unterstuetzen",
    "tätigkeiten",
    "taetigkeiten",
    "stellenbeschreibung",
]

# User-reported context (checkboxes in the form). These are added to the
# rule counts with the severity given here.
CHECKBOXES = [
    {
        "id": "unsolicited",
        "severity": "strong",
        "text_de": "Ich habe mich nicht beworben; das Angebot kam unaufgefordert.",
        "text_en": "I did not apply; the offer reached me unsolicited.",
    },
    {
        "id": "asked_id",
        "severity": "critical",
        "text_de": "Ich wurde gebeten, Ausweis- oder Bankdaten zu schicken oder "
                   "ein Video-Ident zu machen, bevor es einen Vertrag gab.",
        "text_en": "I was asked to send ID or bank details or do a video ident "
                   "before getting a contract.",
    },
    {
        "id": "asked_bank_or_fee",
        "severity": "critical",
        "text_de": "Ich wurde gebeten, ein Bankkonto zu eröffnen oder eine "
                   "Gebühr zu zahlen.",
        "text_en": "I was asked to open a bank account or pay any fee.",
    },
    {
        "id": "contact_messenger",
        "severity": "strong",
        "text_de": "Kontakt nur über WhatsApp oder Telegram.",
        "text_en": "Contact only via WhatsApp/Telegram.",
    },
]

RULES = [
    # ------------------------------------------------------------------
    # CRITICAL — any one means "High risk" (unless downgraded, see above)
    # ------------------------------------------------------------------
    {
        "id": "de_id_video",
        "category": "identity",
        "severity": "critical",
        "pattern": r"video[-\s]?ident\w*",
        "explanation_de": "Sie sollen sich per Video identifizieren, bevor es einen "
                          "Vertrag gibt. Echte Arbeitgeber verlangen das nicht vor "
                          "Vertragsabschluss.",
        "explanation_en": "You are asked to identify yourself by video before any "
                          "contract exists. Real employers do not ask for this "
                          "before a contract is signed.",
    },
    {
        "id": "de_id_check",
        "category": "identity",
        "severity": "critical",
        # NARROWED 2026-11-26: only the noun "Identitätsprüfung" (and its
        # ae spelling) counts as a demand. The earlier pattern also had
        # bare "identifizier\\w*|identifik\\w*", which matched ordinary
        # duty wording — "Du identifizierst Wachstumspotenziale",
        # "Identifikation von Engpässen" — and flagged all 58 High-risk
        # feed rows on that one rule. A bare verb stem is not proof that
        # an identity check is demanded of the applicant. Real scam
        # signals stay covered by de_id_video (Video-Ident) and
        # de_id_copy / de_id_passport (ID copies).
        "pattern": r"identit(?:ae|ä)tspr(?:ue|ü)fung",
        "explanation_de": "Eine Identitätsprüfung wird schon im Bewerbungsverfahren verlangt.",
        "explanation_en": "An identity check is demanded during the application process.",
    },
    {
        "id": "de_id_copy",
        "category": "identity",
        "severity": "critical",
        "pattern": (
            r"personalausweis.{0,40}(foto|kopie|scan|vorder|r(?:ue|ü)ckseite|hochladen|senden|schicken|(?:ue|ü)bermitteln)"
            r"|(foto|kopie|scan).{0,40}personalausweis"
            r"|ausweiskopie|ausweis.{0,20}(foto|kopie|scan)"
            r"|selfie.{0,20}ausweis|ausweis.{0,20}selfie"
        ),
        "explanation_de": "Sie sollen ein Foto oder eine Kopie Ihres Ausweises schicken.",
        "explanation_en": "You are asked to send a photo or copy of your ID card.",
    },
    {
        "id": "de_id_passport",
        "category": "identity",
        "severity": "critical",
        "pattern": (
            r"reisepass.{0,30}(kopie|foto|scan|hochladen|senden|schicken)"
            r"|(kopie|foto|scan).{0,30}reisepass"
            r"|reisepasskopie"
        ),
        "explanation_de": "Sie sollen eine Kopie Ihres Reisepasses schicken.",
        "explanation_en": "You are asked to send a copy of your passport.",
    },
    {
        "id": "de_id_tax",
        "category": "identity",
        "severity": "critical",
        "pattern": r"steuer[-\s]?id\b|steueridentifikationsnummer",
        "explanation_de": "Ihre Steuer-ID wird schon vor einem Vertrag verlangt.",
        "explanation_en": "Your tax ID is demanded before any contract exists.",
    },
    {
        "id": "de_bank_open",
        "category": "bank",
        "severity": "critical",
        "pattern": r"konto.{0,25}(er(?:oe|ö)ffnen|er(?:oe|ö)ffnung)|kontoer(?:oe|ö)ffnung",
        "explanation_de": "Sie sollen ein Bankkonto eröffnen, um den Job zu bekommen.",
        "explanation_en": "You are asked to open a bank account to get the job.",
    },
    {
        "id": "de_bank_tester",
        "category": "bank",
        "severity": "critical",
        "pattern": r"bank[-\s]?tester|kunden[-\s]?service[-\s]?tester|konto.{0,15}testen|kontotester",
        "explanation_de": "Sie sollen als sogenannter Bank-Tester ein Konto testen.",
        "explanation_en": "You are asked to 'test' a bank account as a so-called bank tester.",
    },
    {
        "id": "de_bank_partner",
        "category": "bank",
        "severity": "critical",
        "pattern": r"partnerbank",
        "explanation_de": "Die Rede ist von einer 'Partnerbank', bei der Sie ein Konto "
                          "eröffnen sollen.",
        "explanation_en": "It mentions a 'partner bank' where you are supposed to "
                          "open an account.",
    },
    {
        "id": "de_bank_access",
        "category": "bank",
        "severity": "critical",
        "pattern": r"zugangsdaten|online[-\s]?banking|\bpin\b|\btan\b",
        "explanation_de": "Sie sollen Zugangsdaten, PIN oder TAN weitergeben.",
        "explanation_en": "You are asked to share login details, a PIN or a TAN.",
    },
    {
        "id": "de_forward_finance",
        "category": "forwarding",
        "severity": "critical",
        "pattern": (
            r"finanzagent|zahlungsagent"
            r"|(zahlungen|(?:ue|ü)berweisungen|geld).{0,30}weiterleiten"
            r"|weiterleiten.{0,30}(zahlungen|(?:ue|ü)berweisungen|geld)"
            r"|provision.{0,25}transaktion"
        ),
        "explanation_de": "Sie sollen Geld oder Zahlungen für andere weiterleiten und "
                          "bekommen eine Provision pro Transaktion.",
        "explanation_en": "You are asked to forward money or payments for others and "
                          "get a commission per transaction.",
    },
    {
        "id": "de_forward_parcel",
        "category": "forwarding",
        "severity": "critical",
        "pattern": (
            r"warenagent|paketagent"
            r"|pakete?.{0,30}(annehmen|weiterleiten|umpacken)"
            r"|umpacken.{0,30}pakete?"
        ),
        "explanation_de": "Sie sollen Pakete annehmen, umpacken oder weiterleiten.",
        "explanation_en": "You are asked to receive, repack or forward parcels.",
    },
    {
        "id": "de_pay_first",
        "category": "payment",
        "severity": "critical",
        "pattern": (
            r"vorkasse|anzahlung|kaution"
            r"|bearbeitungsgeb(?:ue|ü)hr|schulungsgeb(?:ue|ü)hr|einzahlung"
            r"|freischaltung.{0,25}geb(?:ue|ü)hr"
            r"|(krypto|bitcoin|usdt).{0,25}einz?ahlen"
            r"|einz?ahlen.{0,25}(krypto|bitcoin|usdt)"
            r"|(krypto|bitcoin|usdt).{0,25}\bein\b"
        ),
        "explanation_de": "Sie sollen zuerst zahlen — Vorkasse, Gebühr oder Einzahlung — "
                          "bevor Sie arbeiten.",
        "explanation_en": "You have to pay first — advance payment, a fee or a "
                          "deposit — before you can work.",
    },
    # ------------------------------------------------------------------
    # STRONG (weight 2)
    # ------------------------------------------------------------------
    {
        "id": "de_easy_noexp",
        "category": "easy_money",
        "severity": "strong",
        "pattern": r"ohne (erfahrung|vorkenntnisse)|keine (erfahrung|vorkenntnisse) (n(?:oe|ö)tig|erforderlich|notwendig)",
        "explanation_de": "Es wird versprochen, dass keine Erfahrung nötig ist.",
        "explanation_en": "It promises that no experience is needed.",
    },
    {
        "id": "de_easy_home",
        "category": "easy_money",
        "severity": "strong",
        "pattern": r"heimarbeit|von zu hause|von daheim",
        "explanation_de": "Die Arbeit soll komplett von zu Hause aus laufen.",
        "explanation_en": "The work is supposed to happen entirely from home.",
    },
    {
        "id": "de_easy_money",
        "category": "easy_money",
        "severity": "strong",
        "pattern": r"schnelles geld|leicht.{0,20}geld|schnell geld verdienen",
        "explanation_de": "Es wird schnelles oder leicht verdientes Geld versprochen.",
        "explanation_en": "It promises fast or easy money.",
    },
    {
        "id": "de_easy_pay",
        "category": "easy_money",
        "severity": "strong",
        "pattern": r"\d{3,}\s?(?:€|eur|euro)\s?(?:pro|/|am|je)\s?(?:tag|stunde)",
        "explanation_de": "Es wird ein sehr hoher Tages- oder Stundenlohn versprochen "
                          "(zum Beispiel mehrere hundert Euro pro Tag).",
        "explanation_en": "It promises a very high daily or hourly wage (for example "
                          "several hundred euros per day).",
    },
    {
        "id": "de_task_review",
        "category": "task_scam",
        "severity": "strong",
        "pattern": r"produkte bewerten|bewerten sie produkte",
        "explanation_de": "Sie sollen Produkte bewerten.",
        "explanation_en": "You are asked to rate products.",
    },
    {
        "id": "de_task_like",
        "category": "task_scam",
        "severity": "strong",
        "pattern": r"videos? liken|videos? mit (like|gef(?:ae|ä)llt)|likes? (vergeben|setzen|kaufen)",
        "explanation_de": "Sie sollen Videos liken.",
        "explanation_en": "You are asked to like videos.",
    },
    {
        "id": "de_task_orders",
        "category": "task_scam",
        "severity": "strong",
        "pattern": r"bestellungen optimieren",
        "explanation_de": "Sie sollen Bestellungen 'optimieren'.",
        "explanation_en": "You are asked to 'optimise' orders.",
    },
    {
        "id": "de_task_complete",
        "category": "task_scam",
        "severity": "strong",
        "pattern": r"aufgaben abschlie(?:ss|ß)en|aufgaben erledigen",
        "explanation_de": "Sie sollen einfache Aufgaben abschließen und dafür bezahlt werden.",
        "explanation_en": "You are asked to complete simple tasks for pay.",
    },
    {
        "id": "de_task_payout",
        "category": "task_scam",
        "severity": "strong",
        "pattern": (
            r"t(?:ae|ä)gliche auszahlung|t(?:ae|ä)glich (ausgezahlt|auszahlung|bezahlt)"
            r"|tagesauszahlung|auszahlung (t(?:ae|ä)glich|jeden tag)"
            r"|jeden tag (ausgezahlt|auszahlung|bezahlt)"
        ),
        "explanation_de": "Es wird eine tägliche Auszahlung versprochen.",
        "explanation_en": "It promises a daily payout.",
    },
    {
        "id": "de_messenger_only",
        "category": "contact",
        "severity": "strong",
        "kind": "messenger_only",
        "pattern": r"(whatsapp|telegram|signal)",
        "explanation_de": "Der einzige Kontaktweg ist WhatsApp, Telegram oder Signal.",
        "explanation_en": "The only way to contact them is WhatsApp, Telegram or Signal.",
    },
    {
        "id": "de_instant",
        "category": "acceptance",
        "severity": "strong",
        "pattern": (
            r"sofortige zusage|sofort (eingestellt|angenommen)"
            r"|ohne vorstellungsgespr(?:ae|ä)ch|kein vorstellungsgespr(?:ae|ä)ch"
            r"|ohne bewerbungsgespr(?:ae|ä)ch|kein bewerbungsgespr(?:ae|ä)ch"
        ),
        "explanation_de": "Es wird eine sofortige Zusage ohne Vorstellungsgespräch versprochen.",
        "explanation_en": "It promises an immediate job offer with no interview.",
    },
    # ------------------------------------------------------------------
    # MILD (weight 1)
    # ------------------------------------------------------------------
    {
        "id": "de_mail_free",
        "category": "contact_email",
        "severity": "mild",
        "pattern": r"[a-z0-9._%+\-]+@(?:gmail|gmx|web\.de|outlook|yahoo|t-online)\.[a-z]{2,}",
        "explanation_de": "Als Firmenkontakt steht eine kostenlose E-Mail-Adresse "
                          "(zum Beispiel Gmail). Kleine seriöse Firmen nutzen sie "
                          "auch, deshalb ist das nur ein schwaches Zeichen.",
        "explanation_en": "The company contact is a free email address (for example "
                          "Gmail). Small legitimate firms use them too, so this is "
                          "only a weak sign.",
    },
    {
        "id": "de_no_company",
        "category": "company",
        "severity": "mild",
        "kind": "no_company",
        "pattern": "",
        "explanation_de": "Es werden weder Firmenname, Adresse noch Impressum genannt.",
        "explanation_en": "No company name, address or legal notice is given.",
    },
    {
        "id": "de_exclaim",
        "category": "style",
        "severity": "mild",
        "kind": "exclamations",
        "pattern": "",
        "explanation_de": "Der Text enthält drei oder mehr Ausrufezeichen.",
        "explanation_en": "The text contains three or more exclamation marks.",
    },
]

# Band labels, in both languages. "few" is always followed by the
# "does not mean trustworthy" line (see de_rules.FEW_NOTE_*).
BAND_LABELS = {
    "high": ("Hohes Risiko", "High risk"),
    "some": ("Einige Warnsignale", "Some warning signs"),
    "few": ("Wenige Warnsignale gefunden", "Few warning signs found"),
}
