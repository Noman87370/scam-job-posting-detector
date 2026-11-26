// All visible UI text lives here, as key -> {de, en}. German uses the
// formal "Sie". Rule explanations for the German checker live in
// backend/rules_de.py; the API returns them.

export const STRINGS = {
  appTitle: {
    de: 'Scam Job Posting Detector (englisches ML-Modell + deutscher Warnsignal-Check)',
    en: 'Scam Job Posting Detector (English ML model + German warning-sign checker)',
  },
  subtitle: {
    de: 'Stellenanzeigen prüfen: Englisch per ML-Modell, Deutsch per Warnsignal-Check. Oder aktuelle Stellenangebote aus Deutschland durchsuchen.',
    en: 'Check job postings: English with an ML model, German with a warning-sign check. Or browse current job listings from Germany.',
  },
  wake: {
    de: 'Kostenloses Hosting: Der erste Aufruf nach einer Pause kann bis zu einer Minute zum Aufwachen brauchen.',
    en: 'Free hosting: the first load after a pause can take up to a minute to wake up.',
  },
  statsActive: {
    de: '{active} aktive Jobs · {total} insgesamt',
    en: '{active} active jobs · {total} total',
  },
  statsFreshness: {
    de: 'Aktualisiert {time}',
    en: 'Updated {time}',
  },
  justNow: {
    de: 'gerade eben',
    en: 'just now',
  },
  minutesAgo: {
    de: 'vor {n} Min.',
    en: '{n} min ago',
  },
  hoursAgo: {
    de: 'vor {n} Std.',
    en: '{n} h ago',
  },
  searchPlaceholder: {
    de: 'Titel, Firma oder Ort suchen…',
    en: 'Search title, company or location…',
  },
  allCategories: {
    de: 'Alle Kategorien',
    en: 'All categories',
  },
  riskHigh: {
    de: 'Hohes Risiko',
    en: 'High risk',
  },
  riskSome: {
    de: 'Einige Warnsignale',
    en: 'Some warning signs',
  },
  riskFew: {
    de: 'Wenige Warnsignale gefunden',
    en: 'Few warning signs found',
  },
  sortNewest: {
    de: 'Neueste zuerst',
    en: 'Newest first',
  },
  sortOldest: {
    de: 'Älteste zuerst',
    en: 'Oldest first',
  },
  loadingJobs: {
    de: 'Jobs werden geladen…',
    en: 'Loading jobs…',
  },
  wakingUp: {
    de: 'Der Server wacht gerade auf — das kann im kostenlosen Tarif bis zu einer Minute dauern. Bitte haben Sie einen Moment Geduld.',
    en: 'The server is waking up — this can take up to a minute on the free tier. Please bear with us for a moment.',
  },
  loadError: {
    de: 'Jobs konnten nicht geladen werden: ',
    en: 'Could not load jobs: ',
  },
  retry: {
    de: 'Erneut versuchen',
    en: 'Try again',
  },
  staleNote: {
    de: 'Zwischengespeicherte Stellenangebote — die Jobquelle ist derzeit nicht erreichbar. Die Angaben sind möglicherweise nicht aktuell.',
    en: 'Showing cached listings — the job source is currently unavailable. These listings may be out of date.',
  },
  emptyJobs: {
    de: 'Keine Stellenangebote gefunden. Passen Sie Suche oder Filter an — oder schauen Sie später wieder vorbei.',
    en: 'No job listings found. Try adjusting your search or filters — or check back later.',
  },
  countJobsOne: {
    de: '1 Job gefunden',
    en: '1 job found',
  },
  countJobsMany: {
    de: '{n} Jobs gefunden',
    en: '{n} jobs found',
  },
  pageOf: {
    de: 'Seite {page} von {pages}',
    en: 'Page {page} of {pages}',
  },
  prevPage: {
    de: '← Zurück',
    en: '← Previous',
  },
  nextPage: {
    de: 'Weiter →',
    en: 'Next →',
  },
  locationNotStated: {
    de: 'Ort nicht angegeben',
    en: 'Location not stated',
  },
  postedOn: {
    de: 'Veröffentlicht am {date}',
    en: 'Posted {date}',
  },
  sourceLabel: {
    de: 'Quelle: {source}',
    en: 'Source: {source}',
  },
  checkThisPosting: {
    de: 'Diese Anzeige prüfen',
    en: 'Check this posting',
  },
  copiedToForm: {
    de: 'Die Anzeige wurde in das Prüfformular unten übernommen. Bitte prüfen Sie den Text und senden Sie die Prüfung selbst ab — das Ergebnis wird nur Ihnen angezeigt und nicht gespeichert.',
    en: 'This listing was copied into the check form below. Please review the text and submit the check yourself — the result is shown only to you and is not stored.',
  },
  showDetails: {
    de: 'Beschreibung anzeigen',
    en: 'Show description',
  },
  hideDetails: {
    de: 'Details ausblenden',
    en: 'Hide details',
  },
  applyOriginal: {
    de: 'Bewerben (Originalanzeige) ↗',
    en: 'Apply (original listing) ↗',
  },
  pushedUp: {
    de: 'Was die Bewertung erhöht hat',
    en: 'What pushed the score up',
  },
  pushedDown: {
    de: 'Was die Bewertung gesenkt hat',
    en: 'What pushed the score down',
  },
  disclaimer: {
    de: 'Dies ist eine statistische Schätzung, kein Beweis. Das Modell übersieht etwa jede vierte betrügerische Anzeige und kann echte Anzeigen fälschlich markieren.',
    en: 'This is a statistical estimate, not proof. The model misses about 1 in 4 scams and can flag real postings.',
  },
  descriptionHeading: {
    de: 'Beschreibung',
    en: 'Description',
  },
  rulesFound: {
    de: 'Gefundene Warnsignale',
    en: 'Warning signs found',
  },
  noRules: {
    de: 'Keine Warnsignale gefunden.',
    en: 'No warning signs found.',
  },
  evidenceLabel: {
    de: 'Beleg:',
    en: 'Evidence:',
  },
  downgradedNote: {
    de: 'Herabgestuft: Der Satz klingt nach einer Tätigkeitsbeschreibung oder einer Prüfung zum Beschäftigungsbeginn.',
    en: 'Downgraded: the sentence looks like a job duty or a right-to-work check at employment start.',
  },
  severityCritical: {
    de: 'Kritisch',
    en: 'Critical',
  },
  severityStrong: {
    de: 'Stark',
    en: 'Strong',
  },
  severityMild: {
    de: 'Schwach',
    en: 'Mild',
  },
  countsLine: {
    de: '{critical} kritisch · {strong} stark · {mild} schwach',
    en: '{critical} critical · {strong} strong · {mild} mild',
  },
  checkHeading: {
    de: 'Eine Anzeige prüfen',
    en: 'Check a posting',
  },
  checkIntro: {
    de: 'Füllen Sie die Felder einer Stellenanzeige aus — oder fügen Sie eine Nachricht ein, die Sie erhalten haben. Englisch wird per ML-Modell bewertet, Deutsch per Warnsignal-Check.',
    en: 'Fill in the fields of a job ad — or paste a message you received. English is scored by the ML model, German by the warning-sign check.',
  },
  postingLangLabel: {
    de: 'Sprache der Anzeige',
    en: 'Posting language',
  },
  postingLangAuto: {
    de: 'Automatisch erkennen',
    en: 'Auto-detect',
  },
  postingLangDe: {
    de: 'Deutsch',
    en: 'German',
  },
  postingLangEn: {
    de: 'Englisch',
    en: 'English',
  },
  tryExample: {
    de: 'Beispiel ausprobieren:',
    en: 'Try an example:',
  },
  scamExample: {
    de: 'Betrugsähnliches Beispiel (fiktiv)',
    en: 'Scam-like example (fictional)',
  },
  normalExample: {
    de: 'Normales Beispiel (fiktiv)',
    en: 'Normal example (fictional)',
  },
  phTitle: {
    de: 'Stellentitel',
    en: 'Job title',
  },
  phCompany: {
    de: 'Firma',
    en: 'Company',
  },
  phLocation: {
    de: 'Ort',
    en: 'Location',
  },
  phSalary: {
    de: 'Gehaltsspanne (falls angegeben)',
    en: 'Salary range (if stated)',
  },
  phDescription: {
    de: 'Stellenbeschreibung',
    en: 'Job description',
  },
  phRequirements: {
    de: 'Anforderungen',
    en: 'Requirements',
  },
  phBenefits: {
    de: 'Leistungen',
    en: 'Benefits',
  },
  phCompanyProfile: {
    de: 'Firmenprofil (falls die Anzeige eines hat)',
    en: 'Company profile (if the ad has one)',
  },
  checkRemote: {
    de: 'Homeoffice möglich',
    en: 'Remote work',
  },
  checkLogo: {
    de: 'Firmenlogo angezeigt',
    en: 'Company logo shown',
  },
  checkQuestions: {
    de: 'Auswahlfragen vorhanden',
    en: 'Screening questions',
  },
  checkSalary: {
    de: 'Gehalt angegeben',
    en: 'Salary stated',
  },
  contextHeading: {
    de: 'Was ist Ihnen sonst noch aufgefallen? (optional — funktioniert auch für Chat-Nachrichten und E-Mails, nur für den deutschen Check)',
    en: 'Anything else you noticed? (optional — also works for chat messages and emails, German check only)',
  },
  ctxUnsolicited: {
    de: 'Ich habe mich nicht beworben; das Angebot kam unaufgefordert.',
    en: 'I did not apply; the offer reached me unsolicited.',
  },
  ctxAskedId: {
    de: 'Ich wurde gebeten, Ausweis- oder Bankdaten zu schicken oder ein Video-Ident zu machen, bevor es einen Vertrag gab.',
    en: 'I was asked to send ID or bank details or do a video ident before getting a contract.',
  },
  ctxAskedBankOrFee: {
    de: 'Ich wurde gebeten, ein Bankkonto zu eröffnen oder eine Gebühr zu zahlen.',
    en: 'I was asked to open a bank account or pay any fee.',
  },
  ctxContactMessenger: {
    de: 'Kontakt nur über WhatsApp oder Telegram.',
    en: 'Contact only via WhatsApp/Telegram.',
  },
  charCount: {
    de: '{n} / 10.000 Zeichen',
    en: '{n} / 10,000 characters',
  },
  tooShort: {
    de: ' — geben Sie insgesamt mindestens 100 Zeichen ein.',
    en: ' — enter at least 100 characters in total.',
  },
  tooLong: {
    de: ' — halten Sie die Eingabe unter 10.000 Zeichen.',
    en: ' — keep the total under 10,000 characters.',
  },
  submitCheck: {
    de: 'Diese Anzeige prüfen',
    en: 'Check this posting',
  },
  scoring: {
    de: 'Wird bewertet…',
    en: 'Scoring…',
  },
  scoringBusy: {
    de: 'Wird bewertet… Beim ersten Aufruf kann der kostenlose Host bis zu einer Minute zum Aufwachen brauchen.',
    en: 'Scoring… the free host may need up to a minute to wake up on first load.',
  },
  privacy: {
    de: 'Eingegebener Text wird nur zur Berechnung des Ergebnisses verarbeitet und nicht gespeichert.',
    en: 'Text you enter is processed only to compute the result and is not stored.',
  },
  scoreError: {
    de: 'Diese Anzeige konnte nicht bewertet werden: ',
    en: 'Could not score this posting: ',
  },
  decisionScore: {
    de: 'Entscheidungswert:',
    en: 'Decision score:',
  },
  highStartsAt: {
    de: '„Hohes Risiko“ beginnt bei',
    en: '“High risk” starts at',
  },
  needsChoiceMixed: {
    de: 'Dieser Text mischt Deutsch und Englisch. Bitte wählen Sie die Sprache der Anzeige.',
    en: 'This text mixes German and English. Please choose the posting language.',
  },
  needsChoiceUnsure: {
    de: 'Wir konnten nicht erkennen, ob dieser Text deutsch oder englisch ist. Bitte wählen Sie die Sprache der Anzeige.',
    en: 'We could not tell whether this text is German or English. Please choose the posting language.',
  },
  unsupported: {
    de: 'Diese Prüfung unterstützt nur deutsche und englische Anzeigen.',
    en: 'This checker supports German and English postings only.',
  },
  detectedLanguage: {
    de: 'Erkannte Sprache: {lang}',
    en: 'Detected language: {lang}',
  },
  detectedNote: {
    de: 'Erkannte Sprache: {lang}. Das Ergebnis kann unzuverlässig sein — bitte wechseln Sie die Sprache der Anzeige.',
    en: 'Detected language: {lang}. The result may be unreliable — please switch the posting language.',
  },
  adviceHeading: {
    de: 'Was Sie jetzt tun sollten',
    en: 'What to do now',
  },
  adviceStop: {
    de: 'Brechen Sie den Kontakt ab.',
    en: 'Stop contact.',
  },
  adviceNoId: {
    de: 'Schicken Sie keine Ausweis- oder Bankdaten und machen Sie kein Video-Ident.',
    en: 'Do not send ID or bank data, and do not do a video ident.',
  },
  adviceKeep: {
    de: 'Bewahren Sie alle Nachrichten und Belege auf.',
    en: 'Keep all messages and evidence.',
  },
  adviceReport: {
    de: 'Melden Sie den Fall der Polizei oder einer Verbraucherzentrale.',
    en: 'Report it to the police or a consumer advice center.',
  },
  adviceLinkText: {
    de: 'Verbraucherzentrale: Gefälschte Stellenanzeigen — was ist Jobscamming?',
    en: 'Consumer advice center: fake job postings — what is job scamming?',
  },
  footerModel: {
    de: 'Modell: TF-IDF (1–2 Gramm) + logistische Regression, trainiert auf dem Kaggle-Datensatz „Real / Fake Job Posting Prediction“ (17.880 Anzeigen; Testdaten 3.139, davon 141 betrügerisch). Gemessene Ergebnisse: Präzision 93,1 %, Recall 76,6 %, PR-AUC 0,917 — 108 von 141 betrügerischen Anzeigen erkannt, 8 Fehlalarme bei 2.998 echten Anzeigen.',
    en: 'Model: TF-IDF (1–2 grams) + logistic regression, trained on the Kaggle “Real / Fake Job Posting Prediction” dataset (17,880 postings; test set 3,139, of which 141 fake). Reported results: precision 93.1%, recall 76.6%, PR-AUC 0.917 — 108 of 141 fake postings caught, 8 false alarms among 2,998 real postings.',
  },
  footerModes: {
    de: 'Englisch: ML-Modell. Deutsch: regelbasierte Prüfung, nicht an gelabelten Daten validiert.',
    en: 'English: ML model. German: rule-based check, not validated on labelled data.',
  },
  footerListings: {
    de: 'Stellenangebote über',
    en: 'Job listings via',
  },
  footerApi: {
    de: '(kostenlose öffentliche API)',
    en: '(free public API)',
  },
}

// Fictional example postings (no real company names). The scam-like
// ones are deliberately loud; the normal ones are ordinary working
// student ads.
export const EXAMPLES_EN = {
  scam: {
    title: 'Earn $4,500 per week working from home — no experience needed',
    company: 'BrightPath Rewards',
    location: 'Remote',
    description:
      'Urgent hiring! Work from home and earn $4,500 per week with no ' +
      'experience needed. Just pay a small registration fee of $99 to start ' +
      'immediately. Send the money via wire transfer now — limited positions, ' +
      'apply today! Contact us on WhatsApp +1 555 010 2030 or email ' +
      'apply@brightpath-rewards.example to get started and earn money fast.',
    requirements: '',
    benefits: 'Unlimited income, work from home, no experience needed',
    company_profile: '',
    salary_range: '$4,500 per week',
    telecommuting: true,
    has_company_logo: false,
    has_questions: false,
    has_salary: true,
  },
  normal: {
    title: 'Working Student Data Analyst (m/f/d)',
    company: 'Harborview Analytics GmbH',
    location: 'Erlangen, Germany',
    description:
      'As a working student in our Data Analytics team in Erlangen you will ' +
      'support data collection, validation and reporting with SQL and Power ' +
      'BI. You will document your results, present them to the team in our ' +
      'weekly meeting, and help maintain our dashboards. The role is 15 to ' +
      '20 hours per week, with flexible hours around your lectures and a ' +
      'hybrid working model.',
    requirements:
      'Enrolled student in computer science, data science or a related ' +
      'field. Knowledge of Python and SQL. Good English skills; German is ' +
      'a plus but not required.',
    benefits: 'Flexible working hours, hybrid working model, mentoring, €16 per hour',
    company_profile:
      'Harborview Analytics is a mid-sized software company in Erlangen ' +
      'that builds data tools for manufacturers. Our team of 40 works ' +
      'closely with customers across Germany.',
    salary_range: '€16 per hour',
    telecommuting: true,
    has_company_logo: true,
    has_questions: true,
    has_salary: true,
  },
}

export const EXAMPLES_DE = {
  scam: {
    title: 'Von zu Hause 500 € pro Tag verdienen – keine Erfahrung nötig',
    company: 'SchnellGeld Service',
    location: 'Remote',
    description:
      'Sofortige Zusage! Verdienen Sie 500 € pro Tag von zu Hause aus, ohne ' +
      'Erfahrung und ohne Vorkenntnisse. Zahlen Sie nur eine kleine ' +
      'Bearbeitungsgebühr von 99 € per Vorkasse, um sofort zu starten. ' +
      'Senden Sie außerdem ein Foto Ihres Personalausweises (Vorder- und ' +
      'Rückseite) zur Identitätsprüfung per Video-Ident. Kontakt nur über ' +
      'WhatsApp +49 170 1234567. Tägliche Auszahlung, schnelles Geld, leicht ' +
      'verdientes Geld! Bewerten Sie Produkte und schließen Sie Aufgaben ' +
      'ab – ganz einfach!',
    requirements: '',
    benefits: 'Tägliche Auszahlung, Arbeit von zu Hause',
    company_profile: '',
    salary_range: '500 € pro Tag',
    telecommuting: true,
    has_company_logo: false,
    has_questions: false,
    has_salary: true,
  },
  normal: {
    title: 'Werkstudent (m/w/d) Datenanalyse',
    company: 'Harborview Analytics GmbH',
    location: 'Erlangen',
    description:
      'Als Werkstudentin oder Werkstudent in unserem Data-Analytics-Team in ' +
      'Erlangen unterstützen Sie die Datenerfassung, -validierung und das ' +
      'Reporting mit SQL und Power BI. Sie dokumentieren Ihre Ergebnisse, ' +
      'präsentieren sie im wöchentlichen Teammeeting und helfen bei der ' +
      'Pflege unserer Dashboards. Die Stelle umfasst 15 bis 20 Stunden pro ' +
      'Woche, mit flexiblen Arbeitszeiten rund um Ihre Vorlesungen und ' +
      'einem hybriden Arbeitsmodell.',
    requirements:
      'Eingeschriebene Studentin oder eingeschriebener Student der ' +
      'Informatik, Data Science oder eines verwandten Fachs. Kenntnisse in ' +
      'Python und SQL. Gute Englischkenntnisse; Deutschkenntnisse sind ein ' +
      'Plus, aber keine Voraussetzung.',
    benefits: 'Flexible Arbeitszeiten, hybrides Arbeitsmodell, Mentoring, 16 € pro Stunde',
    company_profile:
      'Harborview Analytics ist ein mittelständisches Softwareunternehmen ' +
      'in Erlangen, das Datentools für Hersteller entwickelt. Unser Team ' +
      'von 40 Personen arbeitet eng mit Kunden in ganz Deutschland ' +
      'zusammen. Unser Sitz ist in Erlangen, Werner-von-Siemens-Straße 1, ' +
      '91052 Erlangen.',
    salary_range: '16 € pro Stunde',
    telecommuting: true,
    has_company_logo: true,
    has_questions: true,
    has_salary: true,
  },
}
