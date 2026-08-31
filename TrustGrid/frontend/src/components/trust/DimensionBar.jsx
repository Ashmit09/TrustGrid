/**
 * DimensionBar — a labelled progress bar for a single TrustGrid dimension.
 * Value is 0–100.
 */
import React from 'react'

function colorForScore(v) {
  if (v >= 80) return '#22c55e'
  if (v >= 65) return '#3b82f6'
  if (v >= 45) return '#f59e0b'
  return '#ef4444'
}

export default function DimensionBar({ label, value = 70, weight }) {
  const pct   = Math.max(0, Math.min(100, value))
  const color = colorForScore(pct)

  return (
    <div className="tg-dim-row">
      <div className="tg-dim-row__header">
        <span className="tg-dim-row__label">
          {label}
          {weight && (
            <span style={{ marginLeft: 4, fontSize: 11, color: 'var(--text-light)' }}>
              ({weight})
            </span>
          )}
        </span>
        <span className="tg-dim-row__value" style={{ color }}>{Math.round(pct)}</span>
      </div>
      <div className="tg-dim-bar-track">
        <div
          className="tg-dim-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}
