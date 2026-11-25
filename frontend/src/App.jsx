import { useCallback, useEffect, useState } from 'react'
import './App.css'

const CATEGORIES = ['', 'Werkstudent', 'Internship', 'Part-time', 'Full-time', 'Other']
const RISK_BANDS = ['', 'low', 'medium', 'high']
const SORTS = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'risk_desc', label: 'Highest risk first' },
  { value: 'risk_asc', label: 'Lowest risk first' },
]

function RiskMeter({ probability, band }) {
  const pct = Math.round(probability * 100)
  return (
    <div className="risk" title={`Fraud probability ${pct}% — risk band: ${band}`}>
      <div className="risk-bar">
        <div className={`risk-fill risk-${band}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`risk-badge risk-${band}`}>
        {band.toUpperCase()} · {pct}%
      </span>
    </div>
  )
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function JobCard({ job }) {
  const [open, setOpen] = useState(false)
  const indicators = job.indicators || {}
  const present = (indicators.indicators || []).filter((i) => i.present)
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
        <RiskMeter probability={job.fraud_probability} band={job.risk_band} />
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
          <h4>Top signals</h4>
          {(indicators.top_fraud_words || []).length > 0 && (
            <p><strong>Pushing towards fraud:</strong>{' '}
              {(indicators.top_fraud_words || []).map((w) => `${w.word} (+${w.contribution})`).join(', ')}
            </p>
          )}
          {(indicators.top_legit_words || []).length > 0 && (
            <p><strong>Pushing towards legitimate:</strong>{' '}
              {(indicators.top_legit_words || []).map((w) => `${w.word} (${w.contribution})`).join(', ')}
            </p>
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
          <p className="disclaimer">
            This is a risk estimate from a machine-learning model, not a definitive
            verdict. Always verify a posting through the employer&apos;s own channels
            before applying or sharing personal data.
          </p>
        </div>
      )}
    </article>
  )
}

function CheckPosting() {
  const [form, setForm] = useState({
    title: '', company: '', location: '', description: '',
    requirements: '', benefits: '', company_profile: '', salary_range: '',
    telecommuting: false, has_company_logo: false, has_questions: false,
  })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) =>
    setForm({ ...form, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
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
      <p>Paste a job ad and get a fraud risk estimate with an explanation.</p>
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
        <label className="check"><input type="checkbox" checked={form.telecommuting} onChange={set('telecommuting')} /> Remote / telecommuting</label>
        <label className="check"><input type="checkbox" checked={form.has_company_logo} onChange={set('has_company_logo')} /> Company logo shown</label>
        <label className="check"><input type="checkbox" checked={form.has_questions} onChange={set('has_questions')} /> Application questions present</label>
        <button type="submit" disabled={busy}>{busy ? 'Scoring…' : 'Check this posting'}</button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="result">
          <RiskMeter probability={result.fraud_probability} band={result.risk_band} />
          <p>
            Estimated fraud probability: <strong>{Math.round(result.fraud_probability * 100)}%</strong>
            {' '}· Risk band: <strong>{result.risk_band}</strong>
            {' '}· Model threshold for “high”: {Math.round(result.probability_threshold * 100)}%
          </p>
          {(result.top_fraud_words || []).length > 0 && (
            <p><strong>Words pushing towards fraud:</strong>{' '}
              {result.top_fraud_words.map((w) => `${w.word} (+${w.contribution})`).join(', ')}</p>
          )}
          {(result.top_legit_words || []).length > 0 && (
            <p><strong>Words pushing towards legitimate:</strong>{' '}
              {result.top_legit_words.map((w) => `${w.word} (${w.contribution})`).join(', ')}</p>
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
        <h1>🛡️ Scam Job Detector</h1>
        <p>AI-powered job search for Germany — every listing scored for fraud risk.</p>
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
            <option key={r} value={r}>{r ? `Risk: ${r}` : 'Any risk level'}</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </section>

      {loading && <p>Loading jobs…</p>}
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
          “Real / Fake Job Posting Prediction” dataset (17,880 postings).
          Scores are risk estimates, not definitive verdicts.
        </p>
      </footer>
    </div>
  )
}
