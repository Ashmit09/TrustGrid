import React, { useEffect, useState, useCallback } from 'react'
import SellerLayout from '../../layouts/SellerLayout'
import { useAuth } from '../../hooks/useAuth'
import { trustService } from '../../services/trustService'
import TrustScoreGauge from '../../components/trust/TrustScoreGauge'
import DimensionBar from '../../components/trust/DimensionBar'
import '../../components/trust/TrustDashboard.css'
import '../buyer/WhatIf.css'

// ── Helpers ───────────────────────────────────────────────

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

const SELLER_DIM_LABELS = {
  order_fulfillment:       'Order Fulfillment',
  delivery_performance:    'Delivery Performance',
  customer_satisfaction:   'Customer Satisfaction',
  return_dispute_handling: 'Return & Dispute Handling',
  platform_reliability:    'Platform Reliability',
}

const SELLER_DIM_WEIGHTS = {
  order_fulfillment:       '25%',
  delivery_performance:    '25%',
  customer_satisfaction:   '20%',
  return_dispute_handling: '15%',
  platform_reliability:    '15%',
}

const BENEFIT_ICONS = {
  SEARCH_VISIBILITY:    '🔍',
  TRUSTED_BADGE:        '✅',
  REDUCED_PLATFORM_FEE: '💸',
  PROMOTIONAL_CREDITS:  '🎯',
}

// ── Mini score history chart ──────────────────────────────

function ScoreHistoryChart({ history }) {
  if (!history || history.length === 0) {
    return <p className="tg-empty" style={{ padding: '24px 0' }}>No score history yet.</p>
  }
  const scores = history.map(h => h.new_score).reverse()
  const min = Math.max(0, Math.min(...scores) - 50)
  const max = Math.min(1000, Math.max(...scores) + 50)
  const range = max - min || 100

  return (
    <div className="tg-chart-area">
      {scores.map((s, i) => {
        const heightPct = ((s - min) / range) * 100
        return (
          <div
            key={i}
            className="tg-chart-bar"
            data-value={s}
            style={{
              height: `${Math.max(4, heightPct)}%`,
              background: s >= 800 ? '#7c3aed' : s >= 600 ? '#3b82f6' : s >= 400 ? '#f59e0b' : '#ef4444',
              opacity: i === scores.length - 1 ? 1 : 0.5 + 0.5 * (i / scores.length),
            }}
            title={`Score: ${s}`}
          />
        )
      })}
    </div>
  )
}

// ── Seller What If Panel ──────────────────────────────────

function WhatIfPanel({ userId }) {
  const [form,   setForm]   = useState({ completions: 0, cancellations: 0 })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]  = useState(null)

  const run = async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      const data = await trustService.simulate(userId, {
        extra_completions:   form.completions,
        extra_cancellations: form.cancellations,
        extra_returns:       0,
        extra_payments:      0,
      })
      setResult(data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Simulation failed.')
    } finally {
      setLoading(false)
    }
  }

  const delta = result ? result.score_delta : null
  const tierChanged = result && result.projected_tier !== result.current_tier

  return (
    <div className="tg-card tg-full whatif-panel">
      <div className="tg-card__title">
        <span className="tg-card__title-icon">🔮</span>
        What If… (Score Simulator)
      </div>
      <p className="whatif-desc">
        Simulate how your Seller Trust Score would change if you fulfilled or cancelled additional orders.
      </p>

      <div className="whatif-inputs">
        {[
          { key: 'completions',   label: 'Fulfilled Orders',   icon: '📦' },
          { key: 'cancellations', label: 'Seller Cancellations', icon: '❌' },
        ].map(({ key, label, icon }) => (
          <div key={key} className="whatif-input-group">
            <label className="whatif-input-label">
              <span>{icon}</span> {label}
            </label>
            <div className="whatif-spinner">
              <button type="button" className="whatif-btn" onClick={() => setForm(f => ({ ...f, [key]: Math.max(0, f[key] - 1) }))}>−</button>
              <span className="whatif-count">{form[key]}</span>
              <button type="button" className="whatif-btn" onClick={() => setForm(f => ({ ...f, [key]: Math.min(100, f[key] + 1) }))}>+</button>
            </div>
          </div>
        ))}
      </div>

      <button
        className="btn btn-primary whatif-run-btn"
        onClick={run}
        disabled={loading || (form.completions === 0 && form.cancellations === 0)}
      >
        {loading ? 'Simulating…' : 'Run Simulation'}
      </button>

      {error && <p className="whatif-error">{error}</p>}

      {result && (
        <div className="whatif-result">
          <div className="whatif-result__scores">
            <div className="whatif-score-box whatif-score-box--current">
              <div className="whatif-score-box__label">Current Score</div>
              <div className="whatif-score-box__value">{result.current_score}</div>
              <span className={`tier-badge tier-${result.current_tier}`}>{result.current_tier}</span>
            </div>
            <div className="whatif-arrow">
              {delta > 0 ? '↗' : delta < 0 ? '↘' : '→'}
              <span className={`whatif-delta ${delta > 0 ? 'whatif-delta--pos' : delta < 0 ? 'whatif-delta--neg' : ''}`}>
                {delta > 0 ? `+${delta}` : delta}
              </span>
            </div>
            <div className="whatif-score-box whatif-score-box--projected">
              <div className="whatif-score-box__label">Projected Score</div>
              <div className="whatif-score-box__value">{result.projected_score}</div>
              <span className={`tier-badge tier-${result.projected_tier}`}>{result.projected_tier}</span>
            </div>
          </div>

          {tierChanged && (
            <div className="whatif-tier-change">
              🎉 Tier change: <strong>{result.current_tier}</strong> → <strong>{result.projected_tier}</strong>
            </div>
          )}

          {result.points_to_next_tier !== null && result.points_to_next_tier > 0 && (
            <p className="whatif-next-tier">
              After simulation, you still need <strong>{result.points_to_next_tier} more points</strong> to reach the next tier.
            </p>
          )}
          {result.points_to_next_tier === 0 && (
            <p className="whatif-next-tier whatif-next-tier--reached">
              ✅ You would reach the next tier with these actions!
            </p>
          )}

          <div className="whatif-dims">
            <div className="whatif-dims__title">Projected Dimension Scores</div>
            {Object.entries(result.projected_dimensions).map(([key, val]) => (
              <DimensionBar
                key={key}
                label={key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                value={val}
                weight=""
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


// ── Main Component ────────────────────────────────────────

export default function SellerTrustGrid() {
  const { user } = useAuth()
  const userId   = user?.user_id

  const [trust,       setTrust]       = useState(null)
  const [breakdown,   setBreakdown]   = useState(null)
  const [history,     setHistory]     = useState([])
  const [benefits,    setBenefits]    = useState([])
  const [explanation, setExplanation] = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [exporting,   setExporting]   = useState(false)

  const handleExport = useCallback(async () => {
    if (!userId) return
    setExporting(true)
    try {
      const { default: api } = await import('../../services/api')
      const resp = await api.get(`/trust/${userId}/export`, { responseType: 'blob' })
      const url  = URL.createObjectURL(new Blob([resp.data], { type: 'text/csv' }))
      const a    = document.createElement('a')
      a.href     = url
      a.download = `trustgrid_history_${userId}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* silently ignore */ }
    finally  { setExporting(false) }
  }, [userId])

  const load = useCallback(() => {
    if (!userId) return
    setLoading(true)
    Promise.all([
      trustService.getMyTrust().catch(() => null),
      trustService.getBreakdown(userId).catch(() => null),
      trustService.getHistory(userId).catch(() => []),
      trustService.getBenefits(userId).catch(() => ({ benefits: [] })),
      trustService.getExplanation(userId).catch(() => null),
    ])
      .then(([t, b, h, ben, ex]) => {
        if (!t) {
          setError('Failed to load trust profile. Make sure the backend is running.')
          setLoading(false)
          return
        }
        setTrust(t)
        setBreakdown(b)
        setHistory(h || [])
        setBenefits(ben?.benefits || [])
        setExplanation(ex)
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load TrustGrid data. Make sure the backend is running.')
        setLoading(false)
      })
  }, [userId])

  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <SellerLayout>
        <div className="tg-loading">
          <span>Loading your TrustGrid dashboard…</span>
        </div>
      </SellerLayout>
    )
  }

  if (error || !trust) {
    return (
      <SellerLayout>
        <div className="tg-empty">{error || 'No data available.'}</div>
      </SellerLayout>
    )
  }

  const dims  = breakdown?.breakdown || trust?.breakdown || {}
  const recs  = breakdown?.recommendations || []
  const tier  = trust.tier
  const score = trust.trust_score
  const conf  = trust.confidence

  return (
    <SellerLayout>
      <div className="tg-page">

        {/* ── Header ── */}
        <div className="tg-page__header">
          <div>
            <h1 className="tg-page__title">Seller TrustGrid Dashboard</h1>
            <p className="tg-page__subtitle">Your seller trust and performance profile.</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={load}>↻ Refresh</button>
        </div>

        {/* ── Hero — Score Card ── */}
        <div className={`tg-hero tg-hero--${tier}`}>
          <TrustScoreGauge score={score} tier={tier} size={160} />

          <div className="tg-hero__info">
            <div className="tg-hero__badges">
              <span className={`tier-badge tier-${tier}`}>{tier}</span>
              <span className={`confidence-badge conf-${conf}`}>{conf} CONFIDENCE</span>
              <span className="tg-hero__user-id">{userId}</span>
              {benefits.some(b => b.name === 'TRUSTED_BADGE' && b.status === 'active') && (
                <span style={{
                  background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0',
                  padding: '3px 10px', borderRadius: 'var(--radius-full)',
                  fontSize: 'var(--text-xs)', fontWeight: 700,
                }}>
                  ✅ TRUSTED SELLER
                </span>
              )}
            </div>

            <p className="tg-hero__tagline">
              {score >= 800
                ? 'Elite seller — top-tier performance and reliability.'
                : score >= 600
                ? 'Trusted seller — consistent fulfillment and customer satisfaction.'
                : score >= 400
                ? 'Standard seller — build your track record to unlock more benefits.'
                : 'Restricted status — review your fulfillment and delivery performance.'}
            </p>

            {conf === 'LOW' && (
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                LOW confidence means TrustGrid needs more transactional data to accurately assess your seller profile.
              </p>
            )}
          </div>
        </div>

        {/* ── Two-col grid ── */}
        <div className="tg-grid">

          {/* Performance Breakdown */}
          <div className="tg-card">
            <div className="tg-card__title">
              <span className="tg-card__title-icon">📊</span>
              Performance Breakdown
            </div>
            <div className="tg-dims">
              {Object.entries(SELLER_DIM_LABELS).map(([key, label]) => (
                <DimensionBar
                  key={key}
                  label={label}
                  value={dims[key] ?? 70}
                  weight={SELLER_DIM_WEIGHTS[key]}
                />
              ))}
            </div>
          </div>

          {/* Driving Factors */}
          <div className="tg-card">
            <div className="tg-card__title">
              <span className="tg-card__title-icon">🔍</span>
              Key Performance Drivers
            </div>
            {explanation?.driving_factors?.length ? (
              <div className="tg-factors">
                {explanation.driving_factors.map((f, i) => (
                  <div key={i} className={`tg-factor-item tg-factor-item--${f.sentiment}`}>
                    <span className="tg-factor-item__dot" />
                    {f.factor}
                  </div>
                ))}
              </div>
            ) : (
              <p className="tg-empty">Fulfill orders to see performance drivers.</p>
            )}

            {/* Time decay note */}
            <div className="tg-decay-note" style={{ marginTop: 'var(--space-4)' }}>
              <span className="tg-decay-note__icon">⏳</span>
              <span>Recent performance has a <strong>greater influence</strong> on your Trust Score than older activity. (90-day half-life decay)</span>
            </div>
          </div>

          {/* Score History */}
          <div className="tg-card">
            <div className="tg-card__title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>
                <span className="tg-card__title-icon">📈</span>
                Score History
              </span>
              <button
                className="btn btn-secondary"
                style={{ fontSize: '12px', padding: '4px 12px' }}
                onClick={handleExport}
                disabled={exporting}
                title="Download full history as CSV"
              >
                {exporting ? 'Exporting…' : '⬇ Export CSV'}
              </button>
            </div>
            <ScoreHistoryChart history={history} />
            <div className="tg-history" style={{ marginTop: 'var(--space-4)' }}>
              {history.length === 0 ? (
                <p className="tg-empty">No score changes recorded yet.</p>
              ) : (
                history.slice(0, 6).map((h, i) => {
                  const ch   = h.score_change
                  const cls  = ch > 0 ? 'pos' : ch < 0 ? 'neg' : 'zero'
                  const sign = ch > 0 ? '+' : ''
                  return (
                    <div key={i} className="tg-history-item">
                      <span className={`tg-history-item__change tg-history-item__change--${cls}`}>
                        {sign}{ch}
                      </span>
                      <span className="tg-history-item__label">
                        {h.reason || h.event_type || 'Score updated'}
                      </span>
                      <span className="tg-history-item__time">
                        {timeAgo(h.created_at)}
                      </span>
                    </div>
                  )
                })
              )}
            </div>
          </div>

          {/* Seller Benefits */}
          <div className="tg-card">
            <div className="tg-card__title">
              <span className="tg-card__title-icon">🎯</span>
              Seller Benefits
            </div>
            <div className="tg-benefits">
              {benefits.map((b) => (
                <div
                  key={b.name}
                  className={`tg-benefit-item${b.status === 'active' ? ' tg-benefit-item--active' : ''}`}
                >
                  <span className="tg-benefit-item__icon">
                    {b.status === 'active' ? (BENEFIT_ICONS[b.name] || '✓') : '🔒'}
                  </span>
                  <div className="tg-benefit-item__body">
                    <div className="tg-benefit-item__label">{b.label}</div>
                    <div className="tg-benefit-item__desc">{b.description}</div>
                    {b.status !== 'active' && b.reason && (
                      <div className="tg-benefit-item__lock">{b.reason}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Improve Your Score */}
          <div className="tg-card tg-full">
            <div className="tg-card__title">
              <span className="tg-card__title-icon">💡</span>
              Improve Your Score
            </div>
            {recs.length > 0 ? (
              <div className="tg-recs">
                {recs.map((r, i) => (
                  <div key={i} className="tg-rec-item">
                    <span className="tg-rec-item__num">{i + 1}</span>
                    <span className="tg-rec-item__text">{r}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="tg-empty">
                Excellent seller performance! Maintain your standards to stay Elite.
              </p>
            )}
          </div>

          {/* What If Simulator */}
          <WhatIfPanel userId={userId} />

        </div>
      </div>
    </SellerLayout>
  )
}
