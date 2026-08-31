/**
 * TrustScoreGauge — circular SVG gauge showing Trust Score 0–1000.
 * The arc is coloured by the trust tier.
 */
import React, { useEffect, useRef } from 'react'
import '../trust/TrustDashboard.css'

const TIER_COLORS = {
  ELITE:      '#7c3aed',
  TRUSTED:    '#3b82f6',
  STANDARD:   '#f59e0b',
  RESTRICTED: '#ef4444',
}

export default function TrustScoreGauge({ score = 700, tier = 'TRUSTED', size = 160 }) {
  const radius     = 58
  const circumference = 2 * Math.PI * radius
  // Map score 0–1000 to 0–100% of arc
  const pct     = Math.max(0, Math.min(1, score / 1000))
  const offset  = circumference * (1 - pct)
  const color   = TIER_COLORS[tier] || '#3b82f6'
  const cx      = size / 2
  const cy      = size / 2

  return (
    <div
      className="tg-gauge-wrap"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Trust Score: ${score} out of 1000`}
    >
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="tg-gauge__svg"
        style={{ width: size, height: size }}
      >
        {/* Track */}
        <circle
          className="tg-gauge__track"
          cx={cx} cy={cy} r={radius}
          strokeWidth={10}
          fill="none"
          stroke="#e2e8f0"
        />
        {/* Fill */}
        <circle
          className="tg-gauge__fill"
          cx={cx} cy={cy} r={radius}
          strokeWidth={10}
          fill="none"
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{
            transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4,0,0.2,1)',
          }}
        />
      </svg>

      {/* Centred text */}
      <div
        className="tg-gauge__center"
        style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}
      >
        <span className="tg-gauge__score" style={{ color }}>{score}</span>
        <span className="tg-gauge__denom">/1000</span>
      </div>
    </div>
  )
}
