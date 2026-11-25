import { useCallback, useEffect, useState } from 'react'
import './App.css'

// Reported results on the English test set (3,139 postings, 141 fake).
// These are the notebook's numbers — the only metrics shown anywhere
// in the UI. (The retrained model's own measurements live in
// model/METRICS.md.)
const NOTEBOOK_METRICS = {
  precision: '93.1%',
  recall: '76.6%',
  prAuc: '0.917',
  caught: '108 of 141',
  falseAlarms: '8',
  testSize: '3,139',
}

const DISCLAIMER =
  'This is a statistical estimate, not proof. The model misses about ' +
  '1 in 4 scams and can flag real postings.'

const CATEGORIES = ['', 'Werkstudent', 'Internship', 'Part-time', 'Full-time', 'Other']
const RISK_BANDS = [
  { value: '', label: 'Any risk level' },
  { value: 'high', label: 'High risk' },
  { value: 'some', label: 'Some warning signs' },
  { value: 'few', label: 'Few warning signs' },
]
const SORTS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'risk_desc', label: 'Highest risk first' },
  { value: 'risk_asc', label: 'Lowest risk first' },
]

const BAND_LABELS = {
  high: 'High risk',
  some: 'Some warning signs',
  few: 'Few warning signs',
}

// Fictional example postings (no real company names). The scam-like
// one is deliberately loud; the normal one is an ordinary working
// student ad. Both load into the form so visitors can see how the
// fields map to the model.
const EXAMPLES = {
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

function RiskBadge({ band, score }) {
  return (
    <span className={`risk-badge risk-${band}`} title={score != null ? `Decision score ${score}` : ''}>
      {BAND_LABELS[band] || band}
      {score != null ? ` · score ${score}` : ''}
    </span>
  )
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function fmtContribution(c) {
  return c > 0 ? `+${c}` : `${c}`
}

function JobCard({ job }) {
  const [open, setOpen] = useState(false)
  const indicators = job.indicators || {}
  const present = (indicators.indicators || []).filter((i) => i.present)
  // New explanation keys; fall back to the older stored shape.
  const raising = indicators.top_raising
    || (indicators.top_fraud_words || []).map((w) => ({ feature: w.word, contribution: w.contribution }))
  const lowering = indicators.top_lowering
    || (indicators.top_legit_words || []).map((w) => ({ feature: w.word, contribution: w.contribution }))
  const notEnglish = job.language && job.language !== 'en'

  return (
    <article className="card">
      <div className="card-head">
        <div>
          <h3>{job.title}</h3>
          <p className="meta">
            {job.company} · {job.location || 'Location not stated'} · {job.category}
          </p>
          <p className="meta small">Posted {fmtDate(job.posted_at)} · Source: {job.source}</p>
        </div>
        {notEnglish ? (
          <span className="risk-badge risk-unknown" title="The model was trained on English postings only">
            Not scored — not in English
          </span>
        ) : (
          <RiskBadge band={job.risk_band} score={job.decision_score} />
        )}
      </div>
      <p className="snippet">
        {(job.description || '').slice(0, 220)}
        {(job.description || '').length > 220 ? '…' : ''}
      </p>
      {present.length > 0 && (
        <p className="flags">⚠ {present.length} risk indicator{present.length > 1 ? 's' : ''}: {present.map((i) => i.label).join(', ')}</p>
      )}
      <div className="card-actions">
        <button onClick={() => setOpen(!open)}>{open ? 'Hide details' : 'Why this score?'}</button>
        <a href={job.url} target="_blank" rel="noreferrer" className="apply">
          Apply (original listing) ↗
        </a>
      </div>
      {open && (
        <div className="details">
          {notEnglish ? (
            <p className="lang-warning">
              This model was trained on English postings, so the result would be unreliable.
              No risk level is shown for this listing.
            </p>
          ) : (
            <>
              <h4>What pushed the score up</h4>
              {raising.length > 0 ? (
                <p>{raising.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
              ) : (
                <p>Nothing pushed the score up.</p>
              )}
              <h4>What pushed the score down</h4>
              {lowering.length > 0 ? (
                <p>{lowering.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
              ) : (
                <p>Nothing pushed the score down.</p>
              )}
            </>
          )}
          <h4>Indicators checked</h4>
          <ul>
            {(indicators.indicators || []).map((i) => (
              <li key={i.code} className={i.present ? 'bad' : 'good'}>
                {i.present ? '✗' : '✓'} <strong>{i.label}.</strong> {i.detail}
              </li>
            ))}
          </ul>
          <h4>Description</h4>
          <p className="full-desc">{job.description}</p>
          <p className="disclaimer">{DISCLAIMER}</p>
        </div>
      )}
    </article>
  )
}

const EMPTY_FORM = {
  title: '', company: '', location: '', description: '',
  requirements: '', benefits: '', company_profile: '', salary_range: '',
  telecommuting: false, has_company_logo: false, has_questions: false,
  has_salary: false,
}

const TEXT_FIELDS = [
  'title', 'company', 'location', 'description',
  'requirements', 'benefits', 'company_profile', 'salary_range',
]

function CheckPosting() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const totalChars = TEXT_FIELDS.reduce((n, k) => n + (form[k] || '').length, 0)
  const tooShort = totalChars < 100
  const tooLong = totalChars > 10000

  const set = (key) => (e) =>
    setForm({ ...form, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  function loadExample(kind) {
    setForm({ ...EMPTY_FORM, ...EXAMPLES[kind] })
    setResult(null)
    setError('')
  }

  async function submit(e) {
    e.preventDefault()
    if (tooShort || tooLong) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Server returned ${res.status}`)
      }
      setResult(await res.json())
    } catch (err) {
      setError(`Could not score this posting: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="checker">
      <h2>Check a posting</h2>
      <p>
        Fill in the fields of a job ad — the model uses the same fields it
        was trained on. English postings only.
      </p>
      <div className="examples">
        <span>Try an example:</span>
        <button type="button" onClick={() => loadExample('scam')}>Scam-like example (fictional)</button>
        <button type="button" onClick={() => loadExample('normal')}>Normal example (fictional)</button>
      </div>
      <form onSubmit={submit}>
        <div className="grid2">
          <input placeholder="Job title" value={form.title} onChange={set('title')} />
          <input placeholder="Company" value={form.company} onChange={set('company')} />
          <input placeholder="Location" value={form.location} onChange={set('location')} />
          <input placeholder="Salary range (if stated)" value={form.salary_range} onChange={set('salary_range')} />
        </div>
        <textarea placeholder="Job description" rows={5} value={form.description} onChange={set('description')} required />
        <textarea placeholder="Requirements" rows={3} value={form.requirements} onChange={set('requirements')} />
        <textarea placeholder="Benefits" rows={2} value={form.benefits} onChange={set('benefits')} />
        <textarea placeholder="Company profile (if the ad has one)" rows={2} value={form.company_profile} onChange={set('company_profile')} />
        <label className="check"><input type="checkbox" checked={form.telecommuting} onChange={set('telecommuting')} /> Remote work</label>
        <label className="check"><input type="checkbox" checked={form.has_company_logo} onChange={set('has_company_logo')} /> Company logo shown</label>
        <label className="check"><input type="checkbox" checked={form.has_questions} onChange={set('has_questions')} /> Screening questions</label>
        <label className="check"><input type="checkbox" checked={form.has_salary} onChange={set('has_salary')} /> Salary stated</label>
        <p className="char-count">
          {totalChars.toLocaleString()} / 10,000 characters
          {tooShort && ' — enter at least 100 characters in total.'}
          {tooLong && ' — keep the total under 10,000 characters.'}
        </p>
        <button type="submit" disabled={busy || tooShort || tooLong}>{busy ? 'Scoring…' : 'Check this posting'}</button>
      </form>
      <p className="privacy">Text you enter is processed only to compute the result and is not stored.</p>
      {busy && <p>Scoring… the free host may need up to a minute to wake up on first load.</p>}
      {error && <p className="error">{error}</p>}
      {result && !result.language_ok && (
        <div className="result">
          <p className="lang-warning">{result.language_message}</p>
          <p className="disclaimer">{DISCLAIMER}</p>
        </div>
      )}
      {result && result.language_ok && (
        <div className="result">
          <RiskBadge band={result.risk_band} score={result.decision_score} />
          <p>
            Decision score: <strong>{result.decision_score}</strong>
            {' '}· “High risk” starts at <strong>{result.threshold}</strong>
          </p>
          {(result.top_raising || []).length > 0 && (
            <p><strong>What pushed the score up:</strong>{' '}
              {result.top_raising.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
          )}
          {(result.top_lowering || []).length > 0 && (
            <p><strong>What pushed the score down:</strong>{' '}
              {result.top_lowering.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
          )}
          <ul>
            {result.indicators.map((i) => (
              <li key={i.code} className={i.present ? 'bad' : 'good'}>
                {i.present ? '✗' : '✓'} <strong>{i.label}.</strong> {i.detail}
              </li>
            ))}
          </ul>
          <p className="disclaimer">{result.disclaimer}</p>
        </div>
      )}
    </section>
  )
}

export default function App() {
  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState(null)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [riskBand, setRiskBand] = useState('')
  const [sort, setSort] = useState('newest')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({
        page: String(page), per_page: '20', sort,
      })
      if (q) params.set('q', q)
      if (category) params.set('category', category)
      if (riskBand) params.set('risk_band', riskBand)
      const res = await fetch(`/api/jobs?${params}`)
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const data = await res.json()
      setJobs(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(`Could not load jobs: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [q, category, riskBand, sort, page])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    fetch('/api/stats').then((r) => r.json()).then(setStats).catch(() => {})
  }, [])

  const pages = Math.max(1, Math.ceil(total / 20))

  return (
    <div className="app">
      <header>
        <h1>🛡️ Scam Job Posting Detector (English postings)</h1>
        <p>Paste an English job posting and get a risk estimate — or browse live German job listings, scored with the same model.</p>
        <p className="wake">Free hosting: the first load after a pause can take up to a minute to wake up.</p>
        {stats && (
          <p className="stats-line">
            {stats.active_jobs} active jobs · {stats.total_jobs} total ingested
            {stats.last_ingest ? ` · Last update ${fmtDate(stats.last_ingest)}` : ' · No ingestion run yet'}
          </p>
        )}
      </header>

      <section className="filters">
        <input
          placeholder="Search title, company or location…"
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1) }}
        />
        <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1) }}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c || 'All categories'}</option>
          ))}
        </select>
        <select value={riskBand} onChange={(e) => { setRiskBand(e.target.value); setPage(1) }}>
          {RISK_BANDS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </section>

      {loading && <p>Loading jobs… the free host may need up to a minute to wake up on first load.</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && total === 0 && (
        <p className="empty">
          No jobs have been ingested yet. Listings are collected automatically
          every 30 minutes from the Arbeitnow job board (Germany-focused). Check
          back shortly — no placeholder or simulated jobs are shown here.
        </p>
      )}
      {!loading && !error && total > 0 && (
        <>
          <p className="count">{total} job{total === 1 ? '' : 's'} found</p>
          <div className="list">
            {jobs.map((job) => <JobCard key={job.id} job={job} />)}
          </div>
          <div className="pager">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button>
            <span>Page {page} of {pages}</span>
            <button disabled={page >= pages} onClick={() => setPage(page + 1)}>Next →</button>
          </div>
        </>
      )}

      <CheckPosting />

      <footer>
        <p>
          Model: TF-IDF (1–2 grams) + logistic regression, trained on the Kaggle
          “Real / Fake Job Posting Prediction” dataset (17,880 postings; test set{' '}
          {NOTEBOOK_METRICS.testSize}, of which 141 fake). Reported results: precision{' '}
          {NOTEBOOK_METRICS.precision}, recall {NOTEBOOK_METRICS.recall}, PR-AUC{' '}
          {NOTEBOOK_METRICS.prAuc} — {NOTEBOOK_METRICS.caught} fake postings caught,{' '}
          {NOTEBOOK_METRICS.falseAlarms} false alarms among 2,998 real postings.
        </p>
        <p>English postings only. {DISCLAIMER}</p>
        <p>
          Job listings via <a href="https://www.arbeitnow.com">Arbeitnow</a> (free public API).
          Text you enter is processed only to compute the result and is not stored.
        </p>
      </footer>
    </div>
  )
}
