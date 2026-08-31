import React from 'react'
import { Link } from 'react-router-dom'
import './About.css'

const SECTIONS = [
  {
    title: 'What is TrustGrid?',
    body: `TrustGrid is a dynamic trust scoring engine for two-sided e-commerce marketplaces. 
    It evaluates the behavioural history of both buyers and sellers, producing a transparent 
    Trust Score (0–1000) and a Confidence level that together drive marketplace privileges.`,
  },
  {
    title: 'Why does marketplace trust matter?',
    body: `Traditional star ratings and review counts are easy to game, static once submitted, 
    and treat all transactions equally regardless of age. TrustGrid takes a different approach: 
    it models reliability across five behavioural dimensions and applies time decay so that 
    recent activity always counts more than old activity.`,
  },
  {
    title: 'How is the Trust Score calculated?',
    body: `Each user's events — orders, payments, cancellations, returns, reviews — are fed into 
    a Feature Engine that aggregates rates and counts with exponential time decay (90-day half-life). 
    An XGBoost model then estimates a reliability probability for each dimension, which is 
    combined using a weighted formula to produce a score from 0 to 1000.`,
  },
  {
    title: 'What is Confidence?',
    body: `Confidence (LOW / MEDIUM / HIGH) measures how much behavioural evidence exists for a 
    given score. A new user starts at 700/LOW — the score looks good on paper, but there is no 
    evidence yet. Privileges that matter require both a sufficient score and sufficient confidence.`,
  },
  {
    title: 'ML & Time Decay',
    body: `TrustGrid uses XGBoost trained on synthetic behavioural data. A 90-day half-life 
    exponential decay function ensures recent actions carry roughly double the weight of 
    actions from 90 days ago. This is a core design principle: past behaviour informs trust, 
    but present behaviour defines it.`,
  },
]

export default function About() {
  return (
    <div className="about-page">
      <nav className="home-nav" style={{ position: 'sticky', top: 0, zIndex: 100, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)', borderBottom: '1px solid var(--border)' }}>
        <div className="container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 60 }}>
          <Link to="/" style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.5px', textDecoration: 'none' }}>
            Trust<span style={{ color: 'var(--color-primary)' }}>Grid</span>
          </Link>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <Link to="/login"    className="btn btn-secondary btn-sm">Log In</Link>
            <Link to="/register" className="btn btn-primary btn-sm">Get Started</Link>
          </div>
        </div>
      </nav>

      <div className="container about-content">
        <div className="about-hero">
          <h1>About TrustGrid</h1>
          <p>Turning Marketplace Behaviour into Trust.</p>
        </div>

        <div className="about-sections">
          {SECTIONS.map((s) => (
            <div className="about-section card" key={s.title}>
              <h2>{s.title}</h2>
              <p>{s.body}</p>
            </div>
          ))}
        </div>

        <div className="about-tiers card">
          <h2>Trust Tiers</h2>
          <div className="tier-row">
            {[
              { tier: 'RESTRICTED', range: '0–399',    cls: 'tier-RESTRICTED' },
              { tier: 'STANDARD',   range: '400–599',  cls: 'tier-STANDARD'   },
              { tier: 'TRUSTED',    range: '600–799',  cls: 'tier-TRUSTED'    },
              { tier: 'ELITE',      range: '800–1000', cls: 'tier-ELITE'      },
            ].map((t) => (
              <div className="tier-item" key={t.tier}>
                <span className={`tier-badge ${t.cls}`}>{t.tier}</span>
                <span className="tier-range">{t.range}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
