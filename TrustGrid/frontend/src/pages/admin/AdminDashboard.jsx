import React, { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { useNavigate } from 'react-router-dom'
import Navbar from '../../components/common/Navbar'
import api from '../../services/api'
import './AdminDashboard.css'

function StatCard({ label, value, sub, color }) {
  return (
    <div className="admin-stat-card">
      <div className="admin-stat-card__value" style={{ color: color || 'var(--text)' }}>{value}</div>
      <div className="admin-stat-card__label">{label}</div>
      {sub && <div className="admin-stat-card__sub">{sub}</div>}
    </div>
  )
}

function TierBar({ label, count, total, color }) {
  const pct = total > 0 ? (count / total) * 100 : 0
  return (
    <div className="admin-tier-row">
      <div className="admin-tier-row__label">
        <span className={`tier-badge tier-${label}`}>{label}</span>
        <span className="admin-tier-row__count">{count}</span>
      </div>
      <div className="admin-tier-bar-track">
        <div className="admin-tier-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="admin-tier-row__pct">{pct.toFixed(1)}%</span>
    </div>
  )
}

const TIER_COLORS = {
  ELITE:      '#7c3aed',
  TRUSTED:    '#3b82f6',
  STANDARD:   '#f59e0b',
  RESTRICTED: '#ef4444',
}

function timeAgo(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (days > 0)  return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (mins > 0)  return `${mins}m ago`
  return 'just now'
}

// ── Distribution Chart (SVG bar histogram) ────────────────────────────────

function DistributionChart({ labels, counts, color }) {
  const maxCount = Math.max(...counts, 1)
  const BAR_MAX_H = 120   // max bar height px
  const BAR_W     = 36
  const GAP       = 8
  const total     = counts.reduce((s, c) => s + c, 0)

  return (
    <div className="admin-dist-chart-wrap">
      <div className="admin-dist-chart">
        {labels.map((label, i) => {
          const h   = Math.max(4, Math.round((counts[i] / maxCount) * BAR_MAX_H))
          const pct = total > 0 ? ((counts[i] / total) * 100).toFixed(1) : '0.0'
          return (
            <div key={i} className="admin-dist-col">
              <div
                className="admin-dist-bar"
                style={{ height: h, background: color, width: BAR_W, minWidth: BAR_W }}
                title={`${label}: ${counts[i]} users (${pct}%)`}
              />
              <div className="admin-dist-count">{counts[i]}</div>
              <div className="admin-dist-label">{label.replace('–', '–')}</div>
            </div>
          )
        })}
      </div>
      <div className="admin-dist-legend">
        Total: <strong>{total}</strong> user{total !== 1 ? 's' : ''} · Hover bars for details
      </div>
    </div>
  )
}


// ── User Detail Modal ─────────────────────────────────────────────────────────

function MiniSparkline({ history }) {
  if (!history || history.length === 0) return <span style={{ color: 'var(--text-light)', fontSize: 11 }}>No history</span>
  const scores = [...history].reverse().map(h => h.new_score)
  const min = Math.max(0,    Math.min(...scores) - 50)
  const max = Math.min(1000, Math.max(...scores) + 50)
  const range = max - min || 100
  const W = 200, H = 48, PAD = 4
  const pts = scores.map((s, i) => {
    const x = PAD + (i / Math.max(scores.length - 1, 1)) * (W - PAD * 2)
    const y = H - PAD - ((s - min) / range) * (H - PAD * 2)
    return `${x},${y}`
  }).join(' ')
  const last  = scores[scores.length - 1]
  const first = scores[0]
  const up    = last >= first
  return (
    <svg width={W} height={H} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={up ? '#16a34a' : '#dc2626'} strokeWidth="2" strokeLinejoin="round" />
      {scores.map((s, i) => {
        const x = PAD + (i / Math.max(scores.length - 1, 1)) * (W - PAD * 2)
        const y = H - PAD - ((s - min) / range) * (H - PAD * 2)
        return <circle key={i} cx={x} cy={y} r={2.5} fill={up ? '#16a34a' : '#dc2626'} />
      })}
    </svg>
  )
}

function ModalDimBar({ label, value }) {
  const pct = Math.min(100, Math.max(0, value))
  const color = pct >= 75 ? '#16a34a' : pct >= 50 ? '#f59e0b' : '#dc2626'
  return (
    <div className="modal-dim-row">
      <span className="modal-dim-label">{label}</span>
      <div className="modal-dim-track">
        <div className="modal-dim-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="modal-dim-val">{value}</span>
    </div>
  )
}

const DIM_LABELS_BUYER = {
  order_reliability:      'Order Reliability',
  return_behaviour:       'Return Behaviour',
  payment_reliability:    'Payment Reliability',
  cancellation_behaviour: 'Cancellation',
  platform_engagement:    'Engagement',
}
const DIM_LABELS_SELLER = {
  fulfillment_rate:       'Fulfillment',
  delivery_timeliness:    'Delivery',
  rating_quality:         'Rating Quality',
  return_handling:        'Return Handling',
  catalog_quality:        'Catalog Quality',
}

function UserDetailModal({ userId, onClose }) {
  const [profile,   setProfile]   = useState(null)
  const [history,   setHistory]   = useState([])
  const [breakdown, setBreakdown] = useState(null)
  const [loading,   setLoading]   = useState(true)

  useEffect(() => {
    if (!userId) return
    Promise.all([
      api.get(`/trust/${userId}`).then(r => r.data).catch(() => null),
      api.get(`/trust/${userId}/history?limit=30`).then(r => r.data).catch(() => []),
      api.get(`/trust/${userId}/breakdown`).then(r => r.data).catch(() => null),
    ]).then(([p, h, b]) => {
      setProfile(p)
      setHistory(h)
      setBreakdown(b)
      setLoading(false)
    })
  }, [userId])

  if (!userId) return null

  const dimLabels = profile?.role === 'seller' ? DIM_LABELS_SELLER : DIM_LABELS_BUYER
  const dims = breakdown?.dimensions || {}

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
        <div className="modal-header">
          <div>
            <div className="modal-uid">{userId}</div>
            {profile && (
              <div className="modal-name">{profile.name}</div>
            )}
          </div>
          {profile && (
            <div className="modal-badges">
              <span className={`tier-badge tier-${profile.tier}`}>{profile.tier}</span>
              <span className={`confidence-badge conf-${profile.confidence}`}>{profile.confidence}</span>
              <span className={`admin-role-pill admin-role-pill--${profile.role}`}>{profile.role}</span>
            </div>
          )}
        </div>

        {loading ? (
          <div className="modal-loading">Loading profile…</div>
        ) : !profile ? (
          <div className="modal-loading" style={{ color: 'var(--error)' }}>Could not load profile.</div>
        ) : (
          <>
            {/* Score + sparkline */}
            <div className="modal-score-row">
              <div className="modal-score-block">
                <div className="modal-score-val">{profile.trust_score}</div>
                <div className="modal-score-label">Trust Score</div>
              </div>
              <div className="modal-sparkline-block">
                <div className="modal-sparkline-label">Score History ({history.length} entries)</div>
                <MiniSparkline history={history} />
              </div>
            </div>

            {/* Dimension breakdown */}
            {breakdown && Object.keys(dims).length > 0 && (
              <div className="modal-section">
                <div className="modal-section-title">Dimension Breakdown</div>
                {Object.entries(dimLabels).map(([key, label]) =>
                  dims[key] != null ? (
                    <ModalDimBar key={key} label={label} value={Math.round(dims[key])} />
                  ) : null
                )}
              </div>
            )}

            {/* Recent history */}
            {history.length > 0 && (
              <div className="modal-section">
                <div className="modal-section-title">Recent Score Changes</div>
                <div className="modal-history-list">
                  {history.slice(0, 8).map((h, i) => {
                    const pos = h.score_change >= 0
                    return (
                      <div key={i} className="modal-history-row">
                        <span className={`modal-history-delta ${pos ? 'modal-delta-pos' : 'modal-delta-neg'}`}>
                          {pos ? '+' : ''}{h.score_change}
                        </span>
                        <span className="modal-history-score">{h.new_score}</span>
                        <span className="modal-history-reason">{h.reason || h.event_type || '—'}</span>
                        <span className="modal-history-time">{timeAgo(h.created_at)}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}


export default function AdminDashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [analytics,    setAnalytics]    = useState(null)
  const [users,        setUsers]        = useState([])
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState(null)
  const [tab,          setTab]          = useState('overview')
  const [distribution, setDistribution] = useState(null)
  const [selectedUser, setSelectedUser] = useState(null)
  const [anomalies,    setAnomalies]    = useState([])
  const [scanning,     setScanning]     = useState(false)

  useEffect(() => {
    if (user && user.role !== 'admin') {
      navigate('/')
      return
    }
    Promise.all([
      api.get('/admin/analytics').then(r => r.data),
      api.get('/admin/users?limit=50').then(r => r.data),
      api.get('/admin/trust-distribution').then(r => r.data),
      api.get('/admin/anomalies?resolved=false&limit=50').then(r => r.data).catch(() => ({ anomalies: [] })),
    ])
      .then(([a, u, d, an]) => {
        setAnalytics(a)
        setUsers(u.users || [])
        setDistribution(d)
        setAnomalies(an.anomalies || [])
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load admin data.')
        setLoading(false)
      })
  }, [user, navigate])

  if (loading) {
    return (
      <div className="admin-layout">
        <Navbar role="admin" />
        <div className="admin-loading">Loading analytics…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="admin-layout">
        <Navbar role="admin" />
        <div className="admin-error">{error}</div>
      </div>
    )
  }

  const a = analytics || {}
  const tot = a.totals || {}
  const avgs = a.averages || {}
  const buyerTiers  = a.buyer_tiers  || {}
  const sellerTiers = a.seller_tiers || {}
  const confDist    = a.confidence_dist || {}
  const recentChanges = a.recent_changes || []
  const topEvents     = a.top_event_types || []

  const totalBuyerTiers  = Object.values(buyerTiers).reduce((s, v) => s + v, 0)
  const totalSellerTiers = Object.values(sellerTiers).reduce((s, v) => s + v, 0)

  return (
    <div className="admin-layout">
      <Navbar role="admin" />
      <main className="admin-main">
        <div className="admin-container">

          {/* ── Header ── */}
          <div className="admin-header">
            <div>
              <h1 className="admin-title">Admin Dashboard</h1>
              <p className="admin-subtitle">TrustGrid analytics and platform overview</p>
            </div>
            <span className="admin-role-badge">ADMIN</span>
          </div>

          {/* ── Tab bar ── */}
          <div className="admin-tabs">
            {['overview', 'distribution', 'users', 'events', 'alerts'].map(t => (
              <button
                key={t}
                className={`admin-tab${tab === t ? ' admin-tab--active' : ''}`}
                onClick={() => setTab(t)}
              >
                {t === 'alerts' ? (
                  <>Alerts{anomalies.length > 0 && <span className="admin-tab-badge">{anomalies.length}</span>}</>
                ) : (
                  t.charAt(0).toUpperCase() + t.slice(1)
                )}
              </button>
            ))}
          </div>

          {/* ── Overview Tab ── */}
          {tab === 'overview' && (
            <>
              {/* Stat row */}
              <div className="admin-stats-row">
                <StatCard label="Total Buyers"        value={tot.buyers}       />
                <StatCard label="Total Sellers"       value={tot.sellers}      />
                <StatCard label="Total Events"        value={tot.total_events} />
                <StatCard label="Total Orders"        value={tot.total_orders} />
                <StatCard label="Avg Buyer Score"  value={avgs.avg_buyer_score}  color="var(--color-primary)" />
                <StatCard label="Avg Seller Score" value={avgs.avg_seller_score} color="var(--color-accent)"  />
              </div>

              <div className="admin-grid">
                {/* Buyer Tier Distribution */}
                <div className="admin-card">
                  <div className="admin-card__title">Buyer Trust Tiers</div>
                  <div className="admin-tier-list">
                    {['ELITE', 'TRUSTED', 'STANDARD', 'RESTRICTED'].map(t => (
                      <TierBar
                        key={t}
                        label={t}
                        count={buyerTiers[t] || 0}
                        total={totalBuyerTiers}
                        color={TIER_COLORS[t]}
                      />
                    ))}
                  </div>
                </div>

                {/* Seller Tier Distribution */}
                <div className="admin-card">
                  <div className="admin-card__title">Seller Trust Tiers</div>
                  <div className="admin-tier-list">
                    {['ELITE', 'TRUSTED', 'STANDARD', 'RESTRICTED'].map(t => (
                      <TierBar
                        key={t}
                        label={t}
                        count={sellerTiers[t] || 0}
                        total={totalSellerTiers}
                        color={TIER_COLORS[t]}
                      />
                    ))}
                  </div>
                </div>

                {/* Confidence Distribution */}
                <div className="admin-card">
                  <div className="admin-card__title">Confidence Distribution</div>
                  <div className="admin-conf-list">
                    {['HIGH', 'MEDIUM', 'LOW'].map(c => (
                      <div key={c} className="admin-conf-row">
                        <span className={`confidence-badge conf-${c}`}>{c}</span>
                        <span className="admin-conf-count">{confDist[c] || 0} users</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Top Event Types */}
                <div className="admin-card">
                  <div className="admin-card__title">Most Common Events</div>
                  <div className="admin-event-list">
                    {topEvents.map((ev, i) => (
                      <div key={i} className="admin-event-row">
                        <span className="admin-event-type">{ev.event_type.replace(/_/g, ' ')}</span>
                        <span className="admin-event-count">{ev.count.toLocaleString()}</span>
                      </div>
                    ))}
                    {topEvents.length === 0 && (
                      <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>No events yet.</p>
                    )}
                  </div>
                </div>

                {/* Recent Score Changes */}
                <div className="admin-card admin-card--wide">
                  <div className="admin-card__title">Recent Score Changes</div>
                  <div className="admin-changes-list">
                    {recentChanges.length === 0 ? (
                      <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>No score changes yet.</p>
                    ) : (
                      recentChanges.map((ch, i) => {
                        const pos = ch.score_change >= 0
                        return (
                          <div key={i} className="admin-change-row">
                            <span className="admin-change-uid">{ch.user_id}</span>
                            <span className={`admin-change-delta ${pos ? 'admin-change-delta--pos' : 'admin-change-delta--neg'}`}>
                              {pos ? '+' : ''}{ch.score_change}
                            </span>
                            <span className="admin-change-score">{ch.new_score}</span>
                            <span className="admin-change-reason">{ch.reason || '—'}</span>
                            <span className="admin-change-time">{timeAgo(ch.created_at)}</span>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ── Distribution Tab ── */}
          {tab === 'distribution' && (
            <div className="admin-card admin-card--full">
              <div className="admin-card__title">Trust Score Distribution — All Users</div>
              {!distribution ? (
                <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>No data.</p>
              ) : (
                <>
                  {/* Buyers histogram */}
                  <div className="admin-dist-section">
                    <div className="admin-dist-section__label">Buyers</div>
                    <DistributionChart
                      labels={distribution.labels}
                      counts={distribution.buyers}
                      color="#3b82f6"
                    />
                  </div>
                  {/* Sellers histogram */}
                  <div className="admin-dist-section" style={{ marginTop: 32 }}>
                    <div className="admin-dist-section__label">Sellers</div>
                    <DistributionChart
                      labels={distribution.labels}
                      counts={distribution.sellers}
                      color="#7c3aed"
                    />
                  </div>
                </>
              )}
            </div>
          )}

          {/* ── Users Tab ── */}
          {tab === 'users' && (
            <div className="admin-card admin-card--full">
              <div className="admin-card__title">All Users</div>
              <div className="admin-users-table-wrap">
                <table className="admin-users-table">
                  <thead>
                    <tr>
                      <th>User ID</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Score</th>
                      <th>Tier</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(u => (
                      <tr
                        key={u.user_id}
                        className="admin-users-table__row--clickable"
                        onClick={() => setSelectedUser(u.user_id)}
                        title="Click to view full profile"
                      >
                        <td><span className="admin-uid">{u.user_id}</span></td>
                        <td>{u.name}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{u.email}</td>
                        <td>
                          <span className={`admin-role-pill admin-role-pill--${u.role}`}>
                            {u.role}
                          </span>
                        </td>
                        <td><strong>{u.trust_score}</strong></td>
                        <td><span className={`tier-badge tier-${u.tier}`}>{u.tier}</span></td>
                        <td><span className={`confidence-badge conf-${u.confidence}`}>{u.confidence}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Events Tab ── */}
          {tab === 'events' && (
            <div className="admin-card admin-card--full">
              <div className="admin-card__title">Event Type Summary</div>
              <div className="admin-event-grid">
                {topEvents.map((ev, i) => (
                  <div key={i} className="admin-event-card">
                    <div className="admin-event-card__count">{ev.count.toLocaleString()}</div>
                    <div className="admin-event-card__type">{ev.event_type.replace(/_/g, ' ')}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Alerts Tab ── */}
          {tab === 'alerts' && (
            <div className="admin-card admin-card--full">
              <div className="admin-card__title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Anomaly Alerts — Open Flags</span>
                <button
                  className="btn btn-primary"
                  style={{ fontSize: '12px', padding: '5px 14px' }}
                  disabled={scanning}
                  onClick={async () => {
                    setScanning(true)
                    try {
                      await api.post('/admin/anomalies/scan')
                      const res = await api.get('/admin/anomalies?resolved=false&limit=50')
                      setAnomalies(res.data.anomalies || [])
                    } catch { /* ignore */ }
                    finally { setScanning(false) }
                  }}
                >
                  {scanning ? 'Scanning…' : '🔍 Run Scan Now'}
                </button>
              </div>
              {anomalies.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)', padding: 'var(--space-4) 0' }}>
                  No open anomaly flags. Click "Run Scan Now" to check.
                </p>
              ) : (
                <div className="admin-anomaly-list">
                  {anomalies.map(flag => (
                    <div key={flag.flag_id} className={`admin-anomaly-row admin-anomaly-row--${flag.severity.toLowerCase()}`}>
                      <div className="admin-anomaly-meta">
                        <span className={`admin-anomaly-severity admin-anomaly-sev--${flag.severity}`}>{flag.severity}</span>
                        <span className="admin-anomaly-type">{flag.flag_type.replace(/_/g, ' ')}</span>
                        <span className="admin-change-uid">{flag.user_id}</span>
                      </div>
                      <div className="admin-anomaly-desc">{flag.description}</div>
                      <div className="admin-anomaly-actions">
                        <span className="admin-change-time">{timeAgo(flag.created_at)}</span>
                        <button
                          className="admin-anomaly-resolve-btn"
                          onClick={async () => {
                            try {
                              await api.patch(`/admin/anomalies/${flag.flag_id}/resolve`)
                              setAnomalies(prev => prev.filter(f => f.flag_id !== flag.flag_id))
                            } catch { /* ignore */ }
                          }}
                        >
                          Resolve
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>
      </main>

      {/* User Detail Modal */}
      {selectedUser && (
        <UserDetailModal userId={selectedUser} onClose={() => setSelectedUser(null)} />
      )}
    </div>
  )
}
