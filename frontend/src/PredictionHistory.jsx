
import { useCallback, useEffect, useState } from 'react'
import {
  Database,
  RefreshCw,
  Download,
  Eye,
  ShieldAlert,
  CheckCircle2,
  Activity,
  Clock3,
  FileText,
  AlertCircle,
} from 'lucide-react'

const API_URL = 'http://127.0.0.1:8000'

function formatCount(value) {
  return Number(value || 0).toLocaleString()
}

function formatDate(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return value

  return date.toLocaleString()
}

export default function PredictionHistory() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [total, setTotal] = useState(0)
  const [downloadingId, setDownloadingId] = useState(null)
  const [selectedScan, setSelectedScan] = useState(null)
  const [scanDetails, setScanDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [detailsError, setDetailsError] = useState('')
  const [page, setPage] = useState(0)

  const pageSize = 10

  const loadHistory = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch(
        `${API_URL}/api/history?limit=${pageSize}&offset=${page * pageSize}`
      )

      if (!response.ok) {
        throw new Error(`Unable to load history (HTTP ${response.status}).`)
      }

      const data = await response.json()

      setHistory(Array.isArray(data.items) ? data.items : [])
      setTotal(Number(data.total || 0))
    } catch (err) {
      setError(err.message || 'Could not connect to the backend.')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  async function viewDetails(scan) {
    setSelectedScan(scan)
    setScanDetails(null)
    setDetailsError('')
    setDetailsLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/history/${scan.id}`)

      if (!response.ok) {
        throw new Error(`Unable to load scan details (HTTP ${response.status}).`)
      }

      setScanDetails(await response.json())
    } catch (err) {
      setDetailsError(err.message || 'Could not load scan details.')
    } finally {
      setDetailsLoading(false)
    }
  }

  async function downloadScan(scan) {
    setDownloadingId(scan.id)

    try {
      const response = await fetch(
        `${API_URL}/api/history/${scan.id}/download`
      )

      if (!response.ok) {
        throw new Error(`Download failed (HTTP ${response.status}).`)
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')

      link.href = url
      link.download = `history_scan_${scan.id}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.message || 'Unable to download this scan.')
    } finally {
      setDownloadingId(null)
    }
  }

  const totalFlows = history.reduce(
    (sum, scan) => sum + Number(scan.total_flows || 0),
    0
  )

  const totalAttacks = history.reduce(
    (sum, scan) => sum + Number(scan.attack_count || 0),
    0
  )

  const totalBenign = history.reduce(
    (sum, scan) => sum + Number(scan.benign_count || 0),
    0
  )

  return (
    <section className="history-page">
      <div className="history-heading">
        <div>
          <span className="eyebrow">SECURITY OPERATIONS CENTER</span>
          <h2>Prediction History</h2>
          <p>Review previous network traffic scans saved in your database.</p>
        </div>

        <button
          className="secondary-button"
          onClick={loadHistory}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? 'spin' : ''} />
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="history-stats">
        <article className="stat-card">
          <div className="stat-icon blue"><Database size={20} /></div>
          <span>Saved scans</span>
          <strong>{formatCount(total)}</strong>
          <small>Recorded analyses</small>
        </article>

        <article className="stat-card">
          <div className="stat-icon purple"><Activity size={20} /></div>
          <span>Flows on this page</span>
          <strong>{formatCount(totalFlows)}</strong>
          <small>Across the displayed scans</small>
        </article>

        <article className="stat-card">
          <div className="stat-icon red"><ShieldAlert size={20} /></div>
          <span>Potential attacks</span>
          <strong className="danger-text">{formatCount(totalAttacks)}</strong>
          <small>Across the displayed scans</small>
        </article>

        <article className="stat-card">
          <div className="stat-icon green"><CheckCircle2 size={20} /></div>
          <span>Benign flows</span>
          <strong className="success-text">{formatCount(totalBenign)}</strong>
          <small>Across the displayed scans</small>
        </article>
      </div>

      {error && (
        <div className="error-message">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      <article className="panel history-panel">
        <div className="panel-heading">
          <div>
            <h3>Previous scans</h3>
            <p>Newest scans appear first.</p>
          </div>
          <FileText size={21} />
        </div>

        {loading && history.length === 0 ? (
          <div className="history-empty">
            <RefreshCw size={25} className="spin" />
            <span>Loading prediction history…</span>
          </div>
        ) : history.length === 0 ? (
          <div className="history-empty">
            <Database size={30} />
            <strong>No saved scans found</strong>
            <span>Analyze a CSV on the Dashboard to create a history record.</span>
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Scan ID</th>
                    <th>Filename</th>
                    <th>Date and time</th>
                    <th>Total flows</th>
                    <th>Benign</th>
                    <th>Attacks</th>
                    <th>Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {history.map(scan => (
                    <tr key={scan.id}>
                      <td>#{scan.id}</td>
                      <td>{scan.filename}</td>
                      <td>
                        <span className="history-date">
                          <Clock3 size={13} />
                          {formatDate(scan.scanned_at)}
                        </span>
                      </td>
                      <td>{formatCount(scan.total_flows)}</td>
                      <td>
                        <span className="pill benign-pill">
                          {formatCount(scan.benign_count)}
                        </span>
                      </td>
                      <td>
                        <span className="pill attack-pill">
                          {formatCount(scan.attack_count)}
                        </span>
                      </td>
                      <td>
                        <div className="history-actions">
                          <button
                            className="icon-button"
                            title="View scan details"
                            aria-label={`View scan ${scan.id}`}
                            onClick={() => viewDetails(scan)}
                          >
                            <Eye size={16} />
                          </button>

                          <button
                            className="icon-button"
                            title="Download prediction CSV"
                            aria-label={`Download scan ${scan.id}`}
                            disabled={downloadingId === scan.id}
                            onClick={() => downloadScan(scan)}
                          >
                            <Download size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="history-pagination">
              <span>
                Showing {page * pageSize + 1}–
                {page * pageSize + history.length} of {formatCount(total)} scans
              </span>

              <div>
                <button
                  className="secondary-button"
                  disabled={page === 0 || loading}
                  onClick={() => setPage(current => Math.max(0, current - 1))}
                >
                  Previous
                </button>

                <button
                  className="secondary-button"
                  disabled={(page + 1) * pageSize >= total || loading}
                  onClick={() => setPage(current => current + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </article>

      {selectedScan && (
        <div className="modal-backdrop" onClick={() => setSelectedScan(null)}>
          <section
            className="record-modal history-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Saved scan details"
            onClick={event => event.stopPropagation()}
          >
            <div className="panel-heading">
              <div>
                <h3>Scan #{selectedScan.id} details</h3>
                <p>{selectedScan.filename}</p>
              </div>
              <button
                className="icon-button"
                onClick={() => setSelectedScan(null)}
                aria-label="Close details"
              >
                ×
              </button>
            </div>

            {detailsLoading ? (
              <div className="history-empty">
                <RefreshCw size={22} className="spin" />
                <span>Loading scan details…</span>
              </div>
            ) : detailsError ? (
              <div className="error-message">{detailsError}</div>
            ) : scanDetails ? (
              <>
                
            <div className="history-detail-summary">
                <div>
    <span>Scanned at</span>
    <strong>
      {formatDate(
        scanDetails.scanned_at ??
        scanDetails.scan?.scanned_at ??
        selectedScan.scanned_at
      )}
    </strong>
  </div>

  <div>
    <span>Total flows</span>
    <strong>
      {formatCount(
        scanDetails.total_flows ??
        scanDetails.scan?.total_flows ??
        selectedScan.total_flows
      )}
    </strong>
  </div>

  <div>
    <span>Benign</span>
    <strong>
      {formatCount(
        scanDetails.benign_count ??
        scanDetails.scan?.benign_count ??
        selectedScan.benign_count
      )}
    </strong>
  </div>

  <div>
    <span>Potential attacks</span>
    <strong>
      {formatCount(
        scanDetails.attack_count ??
        scanDetails.scan?.attack_count ??
        selectedScan.attack_count
      )}
    </strong>
  </div>
</div>


                <h4>Saved predictions</h4>
                <div className="table-wrap history-detail-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Flow</th>
                        <th>Prediction</th>
                        <th>Attack type</th>
                        <th>Confidence</th>
                        <th>Severity</th>
                        <th>Review priority</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(scanDetails.predictions || []).slice(0, 100).map((item, index) => (
                        <tr key={item.id ?? index}>
                          <td>{item.flow_index ?? '—'}</td>
                          <td>{item.prediction ?? '—'}</td>
                          <td>{item.attack_type ?? '—'}</td>
                          <td>
                            {item.prediction_confidence == null
                              ? '—'
                              : `${Number(item.prediction_confidence).toFixed(2)}%`}
                          </td>
                          <td>{item.severity ?? '—'}</td>
                          <td>{item.review_priority ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {(scanDetails.predictions || []).length > 100 && (
                  <p className="table-note">
                    Showing the first 100 predictions. Download the CSV to view all flows.
                  </p>
                )}

                <button
                  className="primary-button history-download-button"
                  onClick={() => downloadScan(selectedScan)}
                  disabled={downloadingId === selectedScan.id}
                >
                  <Download size={16} /> Download all predictions
                </button>
              </>
            ) : null}
          </section>
        </div>
      )}
    </section>
  )
}
