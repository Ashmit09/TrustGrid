import React from 'react'
import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 16,
      fontFamily: 'var(--font-sans)', color: 'var(--text)',
    }}>
      <span style={{ fontSize: 72, fontWeight: 800, color: 'var(--color-primary)', lineHeight: 1 }}>404</span>
      <h1 style={{ fontSize: 22, fontWeight: 700 }}>Page not found</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>The page you're looking for doesn't exist.</p>
      <Link to="/" className="btn btn-primary">Back to Home</Link>
    </div>
  )
}
