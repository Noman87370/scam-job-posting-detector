import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { STRINGS, EXAMPLES_EN, EXAMPLES_DE } from './i18n.js'

// Replace {name} placeholders in a translated template.
function fmt(template, vars) {
  let out = template || ''
  for (const [k, v] of Object.entries(vars || {})) out = out.replaceAll(`{${k}}`, String(v))
  return out
}

function defaultUiLang() {
  try {
    const saved = localStorage.getItem('uiLang')
    if (saved === 'de' || saved === 'en') return saved
  } catch { /* storage unavailable */ }
  return (navigator.language || 'en').toLowerCase().startsWith('de') ? 'de' : 'en'
}

const CATEGORIES = ['', 'Werkstudent', 'Internship', 'Part-time', 'Full-time', 'Other']
const BAND_VALUES = ['high', 'some', 'few']
const SORT_VALUES = ['newest', 'oldest', 'risk_desc', 'risk_asc']

const BAND_KEY = { high: 'riskHigh', some: 'riskSome', few: 'riskFew' }
const SORT_KEY = {
  newest: 'sortNewest', oldest: 'sortOldest',
  risk_desc: 'sortRiskDesc', risk_asc: 'sortRiskAsc',
}
const SEVERITY_KEY = {
  critical: 'severityCritical', strong: 'severityStrong', mild: 'severityMild',
}

// The four user-reported context checkboxes (German check only).
// Ids match backend/rules_de.py CHECKBOXES.
const CONTEXT_FLAGS = [
  { id: 'unsolicited', key: 'ctxUnsolicited' },
  { id: 'asked_id', key: 'ctxAskedId' },
  { id: 'asked_bank_or_fee', key: 'ctxAskedBankOrFee' },
  { id: 'contact_messenger', key: 'ctxContactMessenger' },
]

function RiskBadge({ band, score, tr }) {
  return (
    <span className={`risk-badge risk-${band}`} title={score != null ? `Decision score ${score}` : ''}>
      {tr(BAND_KEY[band]) || band}
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

function DeRulesList({ matched, checkboxes, tr, uiLang }) {
  const items = matched || []
  const boxes = checkboxes || []
  if (items.length === 0 && boxes.length === 0) return <p>{tr('noRules')}</p>
  return (
    <ul className="rule-list">
      {items.map((m) => (
        <li key={m.rule_id} className={`sev-${m.severity}`}>
          <strong>{tr(SEVERITY_KEY[m.severity])}.</strong>{' '}
          {uiLang === 'de' ? m.explanation_de : m.explanation_en}
          {m.evidence && (
            <span className="evidence"> {tr('evidenceLabel')} “{m.evidence}”</span>
          )}
          {m.downgraded && <span className="downgraded"> {tr('downgradedNote')}</span>}
        </li>
      ))}
      {boxes.map((c) => (
        <li key={c.id} className={`sev-${c.severity}`}>
          <strong>{tr(SEVERITY_KEY[c.severity])}.</strong>{' '}
          {uiLang === 'de' ? c.text_de : c.text_en}
        </li>
      ))}
    </ul>
  )
}

function AdviceBox({ link, tr }) {
  return (
    <div className="advice">
      <h4>{tr('adviceHeading')}</h4>
      <ul>
        <li>{tr('adviceStop')}</li>
        <li>{tr('adviceNoId')}</li>
        <li>{tr('adviceKeep')}</li>
        <li>{tr('adviceReport')}</li>
      </ul>
      <p>
        <a href={link} target="_blank" rel="noreferrer">{tr('adviceLinkText')}</a>
      </p>
    </div>
  )
}

function JobCard({ job, tr, uiLang }) {
  const [open, setOpen] = useState(false)
  const indicators = job.indicators || {}
  const method = indicators.method || 'ml'
  const isDe = job.language === 'de' && method === 'de'
  const isEn = job.language === 'en'
  const present = (indicators.indicators || []).filter((i) => i.present)
  // New explanation keys; fall back to the older stored shape.
  const raising = indicators.top_raising
    || (indicators.top_fraud_words || []).map((w) => ({ feature: w.word, contribution: w.contribution }))
  const lowering = indicators.top_lowering
    || (indicators.top_legit_words || []).map((w) => ({ feature: w.word, contribution: w.contribution }))
  const deMatched = indicators.matched || []

  return (
    <article className="card">
      <div className="card-head">
        <div>
          <h3>{job.title}</h3>
          <p className="meta">
            {job.company} · {job.location || tr('locationNotStated')} · {job.category}
          </p>
          <p className="meta small">
            {fmt(tr('postedOn'), { date: fmtDate(job.posted_at) })} · {fmt(tr('sourceLabel'), { source: job.source })}
          </p>
        </div>
        {isDe ? (
          <div className="badge-col">
            <RiskBadge band={job.risk_band} tr={tr} />
            <span className="method-note">{tr('deMethodNote')}</span>
          </div>
        ) : isEn ? (
          <RiskBadge band={job.risk_band} score={job.decision_score} tr={tr} />
        ) : (
          <span className="risk-badge risk-unknown" title={tr('notScoredTitle')}>
            {tr('notScored')}
          </span>
        )}
      </div>
      <p className="snippet">
        {(job.description || '').slice(0, 220)}
        {(job.description || '').length > 220 ? '…' : ''}
      </p>
      {isDe && (
        <p className="flags">
          {fmt(tr('countsLine'), {
            critical: indicators.critical || 0,
            strong: indicators.strong || 0,
            mild: indicators.mild || 0,
          })}
        </p>
      )}
      {isEn && present.length > 0 && (
        <p className="flags">
          {fmt(tr('riskFlags'), {
            n: present.length,
            plural: present.length > 1 ? 's' : '',
            list: present.map((i) => i.label).join(', '),
          })}
        </p>
      )}
      <div className="card-actions">
        <button onClick={() => setOpen(!open)}>{open ? tr('hideDetails') : tr('whyScore')}</button>
        <a href={job.url} target="_blank" rel="noreferrer" className="apply">
          {tr('applyOriginal')}
        </a>
      </div>
      {open && (
        <div className="details">
          {isDe ? (
            <>
              <h4>{tr('rulesFound')}</h4>
              <DeRulesList matched={deMatched} checkboxes={[]} tr={tr} uiLang={uiLang} />
              <p className="disclaimer">{tr('deMethodNote')}</p>
            </>
          ) : isEn ? (
            <>
              <h4>{tr('pushedUp')}</h4>
              {raising.length > 0 ? (
                <p>{raising.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
              ) : (
                <p>{tr('nothingUp')}</p>
              )}
              <h4>{tr('pushedDown')}</h4>
              {lowering.length > 0 ? (
                <p>{lowering.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
              ) : (
                <p>{tr('nothingDown')}</p>
              )}
              <h4>{tr('indicatorsChecked')}</h4>
              <ul>
                {(indicators.indicators || []).map((i) => (
                  <li key={i.code} className={i.present ? 'bad' : 'good'}>
                    {i.present ? '✗' : '✓'} <strong>{i.label}.</strong> {i.detail}
                  </li>
                ))}
              </ul>
              <h4>{tr('descriptionHeading')}</h4>
              <p className="full-desc">{job.description}</p>
              <p className="disclaimer">{tr('disclaimer')}</p>
            </>
          ) : (
            <p className="lang-warning">{tr('langWarningJob')}</p>
          )}
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

function CheckPosting({ tr, uiLang }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [postingLang, setPostingLang] = useState('auto')
  const [contextFlags, setContextFlags] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const totalChars = TEXT_FIELDS.reduce((n, k) => n + (form[k] || '').length, 0)
  const tooShort = totalChars < 100
  const tooLong = totalChars > 10000

  const set = (key) => (e) =>
    setForm({ ...form, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  function toggleContext(id) {
    setContextFlags((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  function loadExample(kind, lang) {
    const examples = lang === 'de' ? EXAMPLES_DE : EXAMPLES_EN
    setForm({ ...EMPTY_FORM, ...examples[kind] })
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
        body: JSON.stringify({
          ...form,
          posting_language: postingLang,
          context_flags: postingLang === 'en' ? [] : contextFlags,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `Server returned ${res.status}`)
      }
      setResult(await res.json())
    } catch (err) {
      setError(`${tr('scoreError')}${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  const showExamples = postingLang === 'auto' ? ['de', 'en'] : [postingLang]

  return (
    <section className="checker">
      <h2>{tr('checkHeading')}</h2>
      <p>{tr('checkIntro')}</p>
      <div className="lang-row">
        <span>{tr('postingLangLabel')}:</span>
        <label className="radio">
          <input type="radio" name="postingLang" value="auto"
            checked={postingLang === 'auto'} onChange={() => setPostingLang('auto')} />
          {tr('postingLangAuto')}
        </label>
        <label className="radio">
          <input type="radio" name="postingLang" value="de"
            checked={postingLang === 'de'} onChange={() => setPostingLang('de')} />
          {tr('postingLangDe')}
        </label>
        <label className="radio">
          <input type="radio" name="postingLang" value="en"
            checked={postingLang === 'en'} onChange={() => setPostingLang('en')} />
          {tr('postingLangEn')}
        </label>
      </div>
      {showExamples.map((lang) => (
        <div className="examples" key={lang}>
          <span>{tr('tryExample')} {lang === 'de' ? 'Deutsch' : 'English'}:</span>
          <button type="button" onClick={() => loadExample('scam', lang)}>{tr('scamExample')}</button>
          <button type="button" onClick={() => loadExample('normal', lang)}>{tr('normalExample')}</button>
        </div>
      ))}
      <form onSubmit={submit}>
        <div className="grid2">
          <input placeholder={tr('phTitle')} value={form.title} onChange={set('title')} />
          <input placeholder={tr('phCompany')} value={form.company} onChange={set('company')} />
          <input placeholder={tr('phLocation')} value={form.location} onChange={set('location')} />
          <input placeholder={tr('phSalary')} value={form.salary_range} onChange={set('salary_range')} />
        </div>
        <textarea placeholder={tr('phDescription')} rows={5} value={form.description} onChange={set('description')} required />
        <textarea placeholder={tr('phRequirements')} rows={3} value={form.requirements} onChange={set('requirements')} />
        <textarea placeholder={tr('phBenefits')} rows={2} value={form.benefits} onChange={set('benefits')} />
        <textarea placeholder={tr('phCompanyProfile')} rows={2} value={form.company_profile} onChange={set('company_profile')} />
        <label className="check"><input type="checkbox" checked={form.telecommuting} onChange={set('telecommuting')} /> {tr('checkRemote')}</label>
        <label className="check"><input type="checkbox" checked={form.has_company_logo} onChange={set('has_company_logo')} /> {tr('checkLogo')}</label>
        <label className="check"><input type="checkbox" checked={form.has_questions} onChange={set('has_questions')} /> {tr('checkQuestions')}</label>
        <label className="check"><input type="checkbox" checked={form.has_salary} onChange={set('has_salary')} /> {tr('checkSalary')}</label>
        {postingLang !== 'en' && (
          <fieldset className="context">
            <legend>{tr('contextHeading')}</legend>
            {CONTEXT_FLAGS.map((c) => (
              <label className="check" key={c.id}>
                <input type="checkbox" checked={contextFlags.includes(c.id)}
                  onChange={() => toggleContext(c.id)} /> {tr(c.key)}
              </label>
            ))}
          </fieldset>
        )}
        <p className="char-count">
          {fmt(tr('charCount'), { n: totalChars.toLocaleString(uiLang === 'de' ? 'de-DE' : 'en-US') })}
          {tooShort && tr('tooShort')}
          {tooLong && tr('tooLong')}
        </p>
        <button type="submit" disabled={busy || tooShort || tooLong}>{busy ? tr('scoring') : tr('submitCheck')}</button>
      </form>
      <p className="privacy">{tr('privacy')}</p>
      {busy && <p>{tr('scoringBusy')}</p>}
      {error && <p className="error">{error}</p>}
      {result && result.path === 'needs_choice' && (
        <div className="result">
          <p className="lang-warning">{tr(result.mixed ? 'needsChoiceMixed' : 'needsChoiceUnsure')}</p>
          {result.detected_language && (
            <p>{fmt(tr('detectedLanguage'), { lang: result.detected_language })}</p>
          )}
        </div>
      )}
      {result && result.path === 'unsupported' && (
        <div className="result">
          <p className="lang-warning">{tr('unsupported')}</p>
          {result.detected_language && (
            <p>{fmt(tr('detectedLanguage'), { lang: result.detected_language })}</p>
          )}
        </div>
      )}
      {result && result.path === 'de' && (
        <div className="result">
          <RiskBadge band={result.de_band} tr={tr} />
          <p className="method">{uiLang === 'de' ? result.method_label_de : result.method_label_en}</p>
          <p>
            {fmt(tr('countsLine'), {
              critical: result.de_critical, strong: result.de_strong, mild: result.de_mild,
            })}
          </p>
          <h4>{tr('rulesFound')}</h4>
          <DeRulesList matched={result.de_matched} checkboxes={result.de_checkboxes} tr={tr} uiLang={uiLang} />
          {result.de_advice && <AdviceBox link={result.de_advice_link} tr={tr} />}
          {result.de_band === 'few' && (uiLang === 'de' ? result.de_few_note_de : result.de_few_note_en) && (
            <p className="disclaimer">{uiLang === 'de' ? result.de_few_note_de : result.de_few_note_en}</p>
          )}
          <p className="disclaimer">{uiLang === 'de' ? result.disclaimer_de : result.disclaimer}</p>
          {result.detected_language === 'en' && (
            <p className="lang-warning">{fmt(tr('detectedNote'), { lang: 'English' })}</p>
          )}
        </div>
      )}
      {result && result.path === 'ml' && (
        <div className="result">
          <RiskBadge band={result.risk_band} score={result.decision_score} tr={tr} />
          <p>
            {tr('decisionScore')} <strong>{result.decision_score}</strong>
            {' '}· {tr('highStartsAt')} <strong>{result.threshold}</strong>
          </p>
          <p className="method">{uiLang === 'de' ? result.method_label_de : result.method_label_en}</p>
          {(result.top_raising || []).length > 0 && (
            <p><strong>{tr('pushedUp')}:</strong>{' '}
              {result.top_raising.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
          )}
          {(result.top_lowering || []).length > 0 && (
            <p><strong>{tr('pushedDown')}:</strong>{' '}
              {result.top_lowering.map((w) => `${w.feature} (${fmtContribution(w.contribution)})`).join(', ')}</p>
          )}
          <ul>
            {result.indicators.map((i) => (
              <li key={i.code} className={i.present ? 'bad' : 'good'}>
                {i.present ? '✗' : '✓'} <strong>{i.label}.</strong> {i.detail}
              </li>
            ))}
          </ul>
          <p className="disclaimer">{uiLang === 'de' ? result.disclaimer_de : result.disclaimer}</p>
          {result.detected_language && result.detected_language !== 'en' && (
            <p className="lang-warning">
              {fmt(tr('detectedNote'), { lang: result.detected_language })}
            </p>
          )}
        </div>
      )}
    </section>
  )
}

export default function App() {
  const [uiLang, setUiLang] = useState(defaultUiLang)
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

  const tr = (key) => STRINGS[key]?.[uiLang] ?? key

  useEffect(() => {
    try { localStorage.setItem('uiLang', uiLang) } catch { /* storage unavailable */ }
  }, [uiLang])

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
      setError(`${tr('loadError')}${err.message}`)
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
        <div className="header-top">
          <h1>🛡️ {tr('appTitle')}</h1>
          <div className="lang-toggle" role="group" aria-label="Language / Sprache">
            <button type="button" className={uiLang === 'de' ? 'active' : ''}
              onClick={() => setUiLang('de')}>Deutsch</button>
            <button type="button" className={uiLang === 'en' ? 'active' : ''}
              onClick={() => setUiLang('en')}>English</button>
          </div>
        </div>
        <p>{tr('subtitle')}</p>
        <p className="wake">{tr('wake')}</p>
        {stats && (
          <p className="stats-line">
            {fmt(tr('statsActive'), { active: stats.active_jobs, total: stats.total_jobs })}
            {stats.last_ingest ? ` · ${fmt(tr('statsLastUpdate'), { date: fmtDate(stats.last_ingest) })}` : ` · ${tr('statsNoIngest')}`}
          </p>
        )}
      </header>

      <section className="filters">
        <input
          placeholder={tr('searchPlaceholder')}
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1) }}
        />
        <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1) }}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c || tr('allCategories')}</option>
          ))}
        </select>
        <select value={riskBand} onChange={(e) => { setRiskBand(e.target.value); setPage(1) }}>
          <option value="">{tr('anyRisk')}</option>
          {BAND_VALUES.map((b) => (
            <option key={b} value={b}>{tr(BAND_KEY[b])}</option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          {SORT_VALUES.map((s) => <option key={s} value={s}>{tr(SORT_KEY[s])}</option>)}
        </select>
      </section>

      {loading && <p>{tr('loadingJobs')}</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && total === 0 && (
        <p className="empty">{tr('emptyJobs')}</p>
      )}
      {!loading && !error && total > 0 && (
        <>
          <p className="count">{total === 1 ? tr('countJobsOne') : fmt(tr('countJobsMany'), { n: total })}</p>
          <div className="list">
            {jobs.map((job) => <JobCard key={job.id} job={job} tr={tr} uiLang={uiLang} />)}
          </div>
          <div className="pager">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>{tr('prevPage')}</button>
            <span>{fmt(tr('pageOf'), { page, pages })}</span>
            <button disabled={page >= pages} onClick={() => setPage(page + 1)}>{tr('nextPage')}</button>
          </div>
        </>
      )}

      <CheckPosting tr={tr} uiLang={uiLang} />

      <footer>
        <p>{tr('footerModel')}</p>
        <p>{tr('footerModes')} {tr('disclaimer')}</p>
        <p>
          {tr('footerListings')} <a href="https://www.arbeitnow.com">Arbeitnow</a> {tr('footerApi')}.
          {' '}{tr('privacy')}
        </p>
      </footer>
    </div>
  )
}
