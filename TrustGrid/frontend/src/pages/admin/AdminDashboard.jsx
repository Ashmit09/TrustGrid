import React, { useEffect, useState } from 'react'
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


export default function AdminDashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [analytics, setAnalytics] = useState(null)
  const [users,     setUsers]     = useState([])
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(null)
  const [tab,          setTab]          = useState('overview')
  const [distribution, setDistribution] = useState(null)

  useEffect(() => {
    if (user && user.role !== 'admin') {
      navigate('/')
      return
    }
    Promise.all([
      api.get('/admin/analytics').then(r => r.data),
      api.get('/admin/users?limit=20').then(r => r.data),
      api.get('/admin/trust-distribution').then(r => r.data),
    ])
      .then(([a, u, d]) => {
        setAnalytics(a)
        setUsers(u.users || [])
        setDistribution(d)
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
            {['overview', 'distribution', 'users', 'events'].map(t => (
              <button
                key={t}
                className={`admin-tab${tab === t ? ' admin-tab--active' : ''}`}
                onClick={() => setTab(t)}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
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
                      <tr key={u.user_id}>
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

        </div>
      </main>
    </div>
  )
}
