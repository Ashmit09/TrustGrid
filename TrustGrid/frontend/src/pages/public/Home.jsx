import React from 'react'
import { Link } from 'react-router-dom'
import './Home.css'

const HOW_IT_WORKS = [
  {
    step: '01',
    title: 'Marketplace Behaviour',
    desc: 'Every order, payment, cancellation, review, and referral is recorded as a behavioral event.',
  },
  {
    step: '02',
    title: 'TrustGrid Analyses',
    desc: 'Our ML-powered engine evaluates five behavioral dimensions using time-weighted signals. Recent actions matter more.',
  },
  {
    step: '03',
    title: 'Dynamic Benefits',
    desc: 'Your Trust Score (0–1000) and Confidence level determine your marketplace privileges — updated after every action.',
  },
]

const STATS = [
  { value: '0–1000', label: 'Trust Score Range' },
  { value: '5',      label: 'Behavioral Dimensions' },
  { value: '90 days', label: 'Decay Half-Life' },
  { value: '4',      label: 'Trust Tiers' },
]

export default function Home() {
  return (
    <div className="home">
      {/* ── Navbar ── */}
      <nav className="home-nav">
        <div className="container home-nav__inner">
          <span className="home-nav__logo">Trust<span>Grid</span></span>
          <div className="home-nav__links">
            <Link to="/about">About</Link>
            <Link to="/login" className="btn btn-secondary btn-sm">Log In</Link>
            <Link to="/register" className="btn btn-primary btn-sm">Get Started</Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="hero">
        <div className="container hero__inner">
          <div className="hero__badge">Academic Prototype · ML-Powered</div>
          <h1 className="hero__title">
            A Dynamic Trust Engine<br />
            for E-Commerce Marketplaces
          </h1>
          <p className="hero__subtitle">
            TrustGrid evaluates buyer and seller behaviour in real time, producing a
            transparent trust score that drives marketplace privileges — not just a star rating.
          </p>
          <div className="hero__cta">
            <Link to="/register" className="btn btn-primary btn-lg">Create Account</Link>
            <Link to="/login"    className="btn btn-secondary btn-lg">Explore Demo</Link>
          </div>
        </div>
      </section>

      {/* ── Stats bar ── */}
      <section className="stats-bar">
        <div className="container stats-bar__inner">
          {STATS.map((s) => (
            <div className="stat-item" key={s.label}>
              <span className="stat-item__value">{s.value}</span>
              <span className="stat-item__label">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="how-section">
        <div className="container">
          <h2 className="section-title">How TrustGrid Works</h2>
          <p className="section-subtitle">
            Three steps from raw marketplace data to actionable trust.
          </p>
          <div className="how-grid">
            {HOW_IT_WORKS.map((item) => (
              <div className="how-card card" key={item.step}>
                <span className="how-card__step">{item.step}</span>
                <h3 className="how-card__title">{item.title}</h3>
                <p className="how-card__desc">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Score preview ── */}
      <section className="preview-section">
        <div className="container preview__inner">
          <div className="preview__text">
            <h2>Your score tells the full story</h2>
            <p>
              TrustGrid goes beyond total orders and star ratings. It measures
              <strong> how reliably you behave</strong> — and explains every change
              in plain language.
            </p>
            <ul className="preview__bullets">
              <li>✓ 0–1000 Trust Score — dynamic, not static</li>
              <li>✓ LOW / MEDIUM / HIGH Confidence</li>
              <li>✓ Time decay: recent activity matters more</li>
              <li>✓ Explainable: see exactly why your score changed</li>
              <li>✓ Benefits tied to score + confidence</li>
            </ul>
            <Link to="/register" className="btn btn-primary" style={{ marginTop: '20px' }}>
              Register &amp; See Your Score
            </Link>
          </div>
          <div className="preview__card card">
            <div className="preview-score">
              <span className="preview-score__num">824</span>
              <span className="preview-score__denom">/1000</span>
            </div>
            <div className="preview-badges">
              <span className="tier-badge tier-ELITE">Elite</span>
              <span className="confidence-badge conf-HIGH">High Confidence</span>
            </div>
            <div className="preview-dims">
              {[
                ['Order Reliability',      92],
                ['Return Behaviour',        81],
                ['Payment Reliability',     95],
                ['Cancellation Behaviour',  84],
                ['Platform Engagement',     88],
              ].map(([label, val]) => (
                <div className="preview-dim" key={label}>
                  <div className="preview-dim__header">
                    <span>{label}</span><span>{val}/100</span>
                  </div>
                  <div className="preview-dim__bar">
                    <div className="preview-dim__fill" style={{ width: `${val}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="home-footer">
        <div className="container home-footer__inner">
          <span className="home-nav__logo">Trust<span>Grid</span></span>
          <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
            Academic prototype — not a production product.
          </span>
        </div>
      </footer>
    </div>
  )
}
