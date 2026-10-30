import ModelPerformance from './ModelPerformance'
import PredictionHistory from './PredictionHistory'
import { useEffect, useMemo, useState } from 'react'
import {
  ShieldCheck, Upload, FileText, LoaderCircle, AlertCircle, Download,
  Activity, Database, Search, RefreshCw, ShieldAlert, CheckCircle2,
  Clock3, Eye, Gauge, X,
} from 'lucide-react'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import './App.css'

const API_URL = 'http://127.0.0.1:8000'
const COLORS = [
  '#ff5d73', '#21d6a0', '#5d8dff', '#b27aff',
  '#ffb454', '#42c8ef', '#f472b6', '#a3e635',
]

function parseCSV(text) {
  const rows = []
  let row = []
  let cell = ''
  let quoted = false

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]

    if (ch === '"') {
      if (quoted && text[i + 1] === '"') {
        cell += '"'
        i++
      } else {
        quoted = !quoted
      }
    } else if (ch === ',' && !quoted) {
      row.push(cell)
      cell = ''
    } else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && text[i + 1] === '\n') i++
      row.push(cell)
      if (row.some(value => value !== '')) rows.push(row)
      row = []
      cell = ''
    } else {
      cell += ch
    }
  }

  if (cell.length || row.length) {
    row.push(cell)
    if (row.some(value => value !== '')) rows.push(row)
  }

  return rows
}

function severityClass(value) {
  const severity = String(value || '').toLowerCase()
  if (severity === 'critical') return 'severity-critical'
  if (severity === 'high') return 'severity-high'
  if (severity === 'medium') return 'severity-medium'
  if (severity === 'low') return 'severity-low'
  if (severity === 'informational') return 'severity-info'
  return 'severity-unknown'
}

function priorityClass(value) {
  const priority = String(value || '').toLowerCase()
  if (priority.includes('immediate')) return 'priority-immediate'
  if (priority.includes('high')) return 'priority-high'
  if (priority.includes('recommended')) return 'priority-review'
  if (priority === 'routine') return 'priority-routine'
  if (priority === 'monitor') return 'priority-monitor'
  return 'priority-unknown'
}

function confidenceColor(value) {
  if (value >= 90) return '#21d6a0'
  if (value >= 75) return '#5d8dff'
  if (value >= 50) return '#ffb454'
  return '#ff7385'
}

function formatCount(value) {
  return Number(value || 0).toLocaleString()
}

export default function App() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [filter, setFilter] = useState('ALL')
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('Predictions')
  const [apiStatus, setApiStatus] = useState('Checking')
  const [selectedRecord, setSelectedRecord] = useState(null)
  const [currentPage, setCurrentPage] = useState('Dashboard')

  async function checkApi() {
    try {
      const response = await fetch(`${API_URL}/api/health`)
      setApiStatus(response.ok ? 'Online' : 'Unavailable')
    } catch {
      setApiStatus('Offline')
    }
  }

  useEffect(() => {
    checkApi()
  }, [])

  async function handleUpload(event) {
    event.preventDefault()

    if (!file) {
      setError('Please select a CSV file first.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)
    setSelectedRecord(null)
    setFilter('ALL')
    setSeverityFilter('ALL')
    setSearch('')

    try {
      const body = new FormData()
      body.append('file', file)

      const response = await fetch(`${API_URL}/api/predict`, {
        method: 'POST',
        body,
      })

      if (!response.ok) {
        let message = 'Prediction failed. Check the backend and CSV format.'
        try {
          const data = await response.json()
          message = data.detail || message
        } catch {
          // Keep the fallback message if the response isn't JSON.
        }
        throw new Error(
          typeof message === 'string' ? message : JSON.stringify(message)
        )
      }

      const blob = await response.blob()
      const rows = parseCSV(await blob.text())

      if (rows.length < 2) {
        throw new Error('The API returned an empty predictions file.')
      }

      const headers = rows[0].map(header => header.trim())
      const records = rows.slice(1).map(row =>
        Object.fromEntries(
          headers.map((header, index) => [header, row[index] ?? ''])
        )
      )

      const findColumn = name =>
        headers.find(header => header.toLowerCase() === name.toLowerCase())

      const predictionKey = findColumn('Prediction')
      const attackKey = findColumn('Attack Type')
      const confidenceKey = findColumn('Prediction Confidence')
        || findColumn('Attack Confidence')
      const severityKey = findColumn('Severity')
      const priorityKey = findColumn('Review Priority')

      if (!predictionKey || !attackKey) {
        throw new Error('The results CSV is missing prediction columns.')
      }

      const counts = {}
      records.forEach(record => {
        const category = record[attackKey] || 'Unknown'
        counts[category] = (counts[category] || 0) + 1
      })

      setResult({
        records,
        headers,
        counts,
        predictionKey,
        attackKey,
        confidenceKey,
        severityKey,
        priorityKey,
        total: records.length,
        blob,
      })
      setActiveTab('Predictions')
      setApiStatus('Online')
    } catch (err) {
      setError(err.message || 'Unable to connect to the prediction API.')
      checkApi()
    } finally {
      setLoading(false)
    }
  }

  const records = result?.records || []

  const attacks = result
    ? records.filter(record =>
        String(record[result.predictionKey]).toUpperCase() === 'ATTACK'
      ).length
    : 0

  const benign = result ? result.total - attacks : 0

  const distribution = useMemo(() => {
    if (!result) return []
    return Object.entries(result.counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
  }, [result])

  const severityCounts = useMemo(() => {
    const counts = {
      Critical: 0,
      High: 0,
      Medium: 0,
      Low: 0,
      Informational: 0,
    }

    if (result?.severityKey) {
      records.forEach(record => {
        const severity = record[result.severityKey]
        if (Object.prototype.hasOwnProperty.call(counts, severity)) {
          counts[severity]++
        }
      })
    }

    return counts
  }, [records, result])

  const visibleRecords = useMemo(() => {
    if (!result) return []

    return records.filter(record => {
      const prediction = String(
        record[result.predictionKey] || ''
      ).toUpperCase()

      const severity = result.severityKey
        ? String(record[result.severityKey] || '')
        : ''

      const matchesPrediction =
        filter === 'ALL'
        || (filter === 'ATTACK' && prediction === 'ATTACK')
        || (filter === 'BENIGN' && prediction === 'BENIGN')

      const matchesSeverity =
        severityFilter === 'ALL'
        || severity.toLowerCase() === severityFilter.toLowerCase()

      const matchesSearch = !search
        || Object.values(record).some(value =>
          String(value).toLowerCase().includes(search.toLowerCase())
        )

      return matchesPrediction && matchesSeverity && matchesSearch
    })
  }, [records, result, filter, severityFilter, search])

  function downloadResults() {
    if (!result) return

    const url = URL.createObjectURL(result.blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `predictions_${file?.name || 'results.csv'}`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  function renderCell(header, record) {
    const value = record[header] ?? ''

    if (header === result.predictionKey) {
      const isAttack = String(value).toUpperCase() === 'ATTACK'
      return (
        <span className={`pill ${isAttack ? 'attack-pill' : 'benign-pill'}`}>
          {isAttack ? <ShieldAlert size={12} /> : <CheckCircle2 size={12} />}
          {value}
        </span>
      )
    }

    if (header === result.severityKey && result.severityKey) {
      return (
        <span className={`severity-badge ${severityClass(value)}`}>
          <span className="severity-dot" />
          {value || 'Unknown'}
        </span>
      )
    }

    if (header === result.priorityKey && result.priorityKey) {
      return (
        <span className={`priority-badge ${priorityClass(value)}`}>
          {value || 'Not assigned'}
        </span>
      )
    }

    if (header === result.confidenceKey && result.confidenceKey) {
      const confidence = Number(value)
      if (!Number.isFinite(confidence)) return 'N/A'

      const safeConfidence = Math.max(0, Math.min(100, confidence))

      return (
        <div className="confidence-cell">
          <div className="confidence-topline">
            <span>{safeConfidence.toFixed(2)}%</span>
          </div>
          <div
            className="confidence-track"
            role="progressbar"
            aria-label={`Prediction confidence ${safeConfidence.toFixed(2)} percent`}
            aria-valuenow={safeConfidence}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="confidence-fill"
              style={{
                width: `${safeConfidence}%`,
                background: confidenceColor(safeConfidence),
              }}
            />
          </div>
        </div>
      )
    }

    return String(value).slice(0, 100)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><ShieldCheck size={24} /></div>
          <div>
            <strong>CyberGuard</strong>
            <span>SECURITY PLATFORM</span>
          </div>
        </div>

        <div className="nav-label">SECURITY CENTER</div>
        <button
          className={`nav-item nav-button ${currentPage === 'Dashboard' ? 'active' : ''}`}
          onClick={() => setCurrentPage('Dashboard')}
        >
          <Activity size={18} /> Dashboard
        </button>
        <button
          className={`nav-item nav-button ${currentPage === 'Model Performance' ? 'active' : ''}`}
          onClick={() => setCurrentPage('Model Performance')}
        >
          <Gauge size={18} /> Model Performance
        </button>
        <button
          className={`nav-item nav-button ${currentPage === 'Prediction History' ? 'active' : ''}`}
          onClick={() => setCurrentPage('Prediction History')}
        >
          <Clock3 size={18} /> Prediction History
        </button>
        <button
          className="nav-item nav-button"
          onClick={() => {
            setCurrentPage('Dashboard')
            setTimeout(() => document.getElementById('upload-panel')?.scrollIntoView({ behavior: 'smooth' }), 0)
          }}
        >
          <Upload size={18} /> Upload &amp; Analyze
        </button>
        <button
          className="nav-item nav-button"
          onClick={() => {
            setCurrentPage('Dashboard')
            setActiveTab('Attack breakdown')
            setTimeout(() => document.getElementById('results-panel')?.scrollIntoView({ behavior: 'smooth' }), 0)
          }}
        >
          <ShieldAlert size={18} /> Threat Intelligence
        </button>
        <button
          className="nav-item nav-button"
          onClick={() => {
            setCurrentPage('Dashboard')
            setTimeout(() => document.getElementById('charts-panel')?.scrollIntoView({ behavior: 'smooth' }), 0)
          }}
        >
          <Database size={18} /> Traffic Analytics
        </button>
        <button
          className="nav-item nav-button"
          onClick={() => {
            if (currentPage !== 'Dashboard') {
              setCurrentPage('Dashboard')
              setTimeout(downloadResults, 0)
            } else {
              downloadResults()
            }
          }}
          disabled={!result}
        >
          <FileText size={18} /> Export Report
        </button>

        <div className="sidebar-status">
          <span className={`status-dot ${apiStatus === 'Online' ? '' : 'status-warning'}`} />
          <span>Backend API: {apiStatus}</span>
          <button
            className="icon-button"
            onClick={checkApi}
            title="Refresh API status"
            aria-label="Refresh API status"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="eyebrow">SECURITY OPERATIONS CENTER</span>
            <h1>Network Security Overview</h1>
          </div>
          <div className={`api-status ${apiStatus === 'Online' ? 'online' : ''}`}>
            <span className="status-dot" />
            {apiStatus === 'Checking' ? 'Checking API…' : `Backend ${apiStatus}`}
          </div>
        </header>

        {currentPage === 'Model Performance' ? (
          <ModelPerformance />
        ) : currentPage === 'Prediction History' ? (
          <PredictionHistory />
        ) : (
          <>
        <section className="welcome">
          <div>
            <span className="eyebrow">ML-POWERED · CICIDS2017</span>
            <h2>Detect threats. Protect your network.</h2>
            <p>
              Analyze network-flow data and identify potentially malicious
              traffic with your trained machine-learning models.
            </p>
            <button
              className="primary-button"
              onClick={() => document.getElementById('upload-panel')?.scrollIntoView({ behavior: 'smooth' })}
            >
              <Upload size={17} /> Upload traffic CSV
            </button>
          </div>
          <div className="welcome-icon"><ShieldCheck size={44} /></div>
        </section>

        <section className="stats-grid">
          <article className="stat-card">
            <div className="stat-icon blue"><Database size={20} /></div>
            <span>Total flows analyzed</span>
            <strong>{result ? formatCount(result.total) : '—'}</strong>
            <small>{result ? 'Rows in latest analysis' : 'Upload a file to begin'}</small>
          </article>
          <article className="stat-card">
            <div className="stat-icon red"><ShieldAlert size={20} /></div>
            <span>Potential attacks</span>
            <strong className="danger-text">{result ? formatCount(attacks) : '—'}</strong>
            <small>{result ? `${(attacks / result.total * 100).toFixed(1)}% of analyzed flows` : 'Awaiting analysis'}</small>
          </article>
          <article className="stat-card">
            <div className="stat-icon green"><CheckCircle2 size={20} /></div>
            <span>Benign flows</span>
            <strong className="success-text">{result ? formatCount(benign) : '—'}</strong>
            <small>{result ? `${(benign / result.total * 100).toFixed(1)}% of analyzed flows` : 'Awaiting analysis'}</small>
          </article>
          <article className="stat-card">
            <div className="stat-icon purple"><Activity size={20} /></div>
            <span>Predicted categories</span>
            <strong>{result ? distribution.length : '—'}</strong>
            <small>Distinct output classes</small>
          </article>
        </section>

        {result && result.severityKey && (
          <section className="severity-summary">
            {[
              { label: 'Critical', color: 'critical', icon: ShieldAlert },
              { label: 'High', color: 'high', icon: AlertCircle },
              { label: 'Medium', color: 'medium', icon: Eye },
              { label: 'Low', color: 'low', icon: Gauge },
            ].map(item => {
              const Icon = item.icon
              return (
                <article className={`severity-summary-card ${item.color}`} key={item.label}>
                  <div className="severity-summary-icon"><Icon size={18} /></div>
                  <div>
                    <span>{item.label} severity</span>
                    <strong>{formatCount(severityCounts[item.label])}</strong>
                  </div>
                </article>
              )
            })}
          </section>
        )}

        <section className="charts-grid" id="charts-panel">
          <article className="panel chart-panel">
            <div className="panel-heading">
              <div>
                <h3>Attack distribution</h3>
                <p>Breakdown of classified traffic</p>
              </div>
            </div>

            {result ? (
              <>
                <div className="donut-wrap">
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={distribution}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={62}
                        outerRadius={88}
                        paddingAngle={3}
                        stroke="none"
                      >
                        {distribution.map((entry, index) => (
                          <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#11192a', border: '1px solid #34445e', borderRadius: 8 }}
                        formatter={value => [formatCount(value), 'Flows']}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="donut-center">
                    <strong>{formatCount(result.total)}</strong>
                    <span>Total flows</span>
                  </div>
                </div>

                <div className="legend-list">
                  {distribution.slice(0, 8).map((item, index) => (
                    <div className="legend-row" key={item.name}>
                      <span className="legend-name">
                        <i style={{ background: COLORS[index % COLORS.length] }} />
                        {item.name}
                      </span>
                      <strong>{formatCount(item.value)}</strong>
                      <small>{(item.value / result.total * 100).toFixed(1)}%</small>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-chart">
                <Activity size={28} />
                <span>Analyze a CSV to view attack distribution</span>
              </div>
            )}
          </article>

          <article className="panel chart-panel">
            <div className="panel-heading">
              <div>
                <h3>Traffic by category</h3>
                <p>Flow count for each prediction class</p>
              </div>
            </div>

            {result ? (
              <ResponsiveContainer
                width="100%"
                height={Math.max(250, distribution.slice(0, 8).length * 39)}
              >
                <BarChart
                  data={distribution.slice(0, 8)}
                  layout="vertical"
                  margin={{ top: 4, right: 8, left: 12, bottom: 4 }}
                >
                  <CartesianGrid stroke="#26334a" horizontal={false} />
                  <XAxis type="number" tick={{ fill: '#91a2ba', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={95} tick={{ fill: '#c3cee0', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: '#11192a', border: '1px solid #34445e', borderRadius: 8 }} />
                  <Bar dataKey="value" name="Flows" radius={[0, 5, 5, 0]}>
                    {distribution.slice(0, 8).map((item, index) => (
                      <Cell key={item.name} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-chart">
                <Database size={28} />
                <span>Category comparisons appear after analysis</span>
              </div>
            )}
          </article>
        </section>

        <section className="analysis-grid">
          <article className="panel upload-panel" id="upload-panel">
            <div className="panel-heading">
              <div>
                <h3>Analyze network traffic</h3>
                <p>Upload a compatible CICIDS2017-format CSV.</p>
              </div>
              <Upload size={21} />
            </div>

            <form onSubmit={handleUpload}>
              <label className="drop-zone">
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={event => {
                    setFile(event.target.files?.[0] || null)
                    setError('')
                    setResult(null)
                    setSelectedRecord(null)
                  }}
                />
                <div className="upload-icon"><Upload size={25} /></div>
                <strong>{file ? file.name : 'Choose a CSV file'}</strong>
                <span>
                  {file
                    ? `${(file.size / 1048576).toFixed(2)} MB · CSV file`
                    : 'Click to browse your computer'}
                </span>
              </label>

              <div className="upload-actions">
                <span className="hint">Maximum file size: 100 MB</span>
                <button type="submit" disabled={loading || !file}>
                  {loading
                    ? <><LoaderCircle className="spin" size={16} /> Analyzing…</>
                    : <><ShieldCheck size={16} /> Analyze traffic</>}
                </button>
              </div>
            </form>

            {error && (
              <div className="error-message">
                <AlertCircle size={17} /> {error}
              </div>
            )}
          </article>

          <article className="panel results-panel" id="results-panel">
            <div className="panel-heading">
              <div>
                <h3>Traffic investigation</h3>
                <p>
                  {result
                    ? `${formatCount(result.total)} predictions from the latest upload`
                    : 'Prediction details will appear here'}
                </p>
              </div>
              {result && (
                <button className="secondary-button" onClick={downloadResults}>
                  <Download size={15} /> Export CSV
                </button>
              )}
            </div>

            <div className="tabs">
              {['Predictions', 'Attack breakdown'].map(tab => (
                <button
                  key={tab}
                  className={activeTab === tab ? 'tab active-tab' : 'tab'}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>

            {!result ? (
              <div className="empty-results">
                <FileText size={28} />
                <strong>No analysis yet</strong>
                <span>Upload a CSV file to populate the investigation table.</span>
              </div>
            ) : activeTab === 'Attack breakdown' ? (
              <div className="breakdown-list">
                {distribution.map((item, index) => (
                  <div className="breakdown-row" key={item.name}>
                    <span className="category-dot" style={{ background: COLORS[index % COLORS.length] }} />
                    <span>{item.name}</span>
                    <strong>{formatCount(item.value)}</strong>
                    <small>{(item.value / result.total * 100).toFixed(2)}%</small>
                  </div>
                ))}
              </div>
            ) : (
              <>
                <div className="table-controls">
                  <div className="search-box">
                    <Search size={15} />
                    <input
                      value={search}
                      onChange={event => setSearch(event.target.value)}
                      placeholder="Search predictions…"
                    />
                    {search && (
                      <button
                        className="clear-search"
                        onClick={() => setSearch('')}
                        aria-label="Clear search"
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>

                  <select value={filter} onChange={event => setFilter(event.target.value)}>
                    <option value="ALL">All traffic</option>
                    <option value="ATTACK">Attacks only</option>
                    <option value="BENIGN">Benign only</option>
                  </select>

                  {result.severityKey && (
                    <select
                      value={severityFilter}
                      onChange={event => setSeverityFilter(event.target.value)}
                    >
                      <option value="ALL">All severity</option>
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                      <option value="Informational">Informational</option>
                    </select>
                  )}
                </div>

                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {result.headers.map(header => (
                          <th key={header}>{header}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRecords.slice(0, 10).map((record, index) => (
                        <tr
                          key={`${record['Flow Index'] ?? index}-${index}`}
                          className="investigation-row"
                          onClick={() => setSelectedRecord(record)}
                          title="Click to inspect this flow"
                        >
                          {result.headers.map(header => (
                            <td key={header}>{renderCell(header, record)}</td>
                          ))}
                        </tr>
                      ))}
                      {visibleRecords.length === 0 && (
                        <tr>
                          <td colSpan={result.headers.length} className="no-results">
                            No records match the selected filters.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <p className="table-note">
                  Showing {Math.min(10, visibleRecords.length)} of {formatCount(visibleRecords.length)} matching records.
                  {' '}Export CSV for the full result set.
                </p>
              </>
            )}
          </article>
        </section>

        {selectedRecord && result && (
          <div className="modal-backdrop" onClick={() => setSelectedRecord(null)}>
            <section
              className="record-modal"
              role="dialog"
              aria-modal="true"
              aria-label="Flow investigation details"
              onClick={event => event.stopPropagation()}
            >
              <div className="panel-heading">
                <div>
                  <h3>Flow investigation</h3>
                  <p>Model output and available record fields</p>
                </div>
                <button className="icon-button" onClick={() => setSelectedRecord(null)} aria-label="Close details">
                  <X size={18} />
                </button>
              </div>
              <div className="record-details">
                {result.headers.map(header => (
                  <div className="record-detail" key={header}>
                    <span>{header}</span>
                    <strong>{String(selectedRecord[header] ?? '—')}</strong>
                  </div>
                ))}
              </div>
              <p className="table-note">
                Severity and review priority are heuristic suggestions. Model confidence is not a guarantee of correctness.
              </p>
            </section>
          </div>
        )}

        <footer>
          CyberGuard · ML-assisted network traffic classification · Research and demonstration use
        </footer>
          </>
        )}
      </main>
    </div>
  )
}
