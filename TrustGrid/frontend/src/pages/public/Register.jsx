import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authService } from '../../services/authService'
import './Auth.css'

export default function Register() {
  const navigate = useNavigate()
  const [form, setForm]       = useState({ name: '', email: '', password: '', role: 'buyer' })
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await authService.register(form)
      const role = data.user.role
      if (role === 'buyer')  navigate('/buyer/dashboard')
      else if (role === 'seller') navigate('/seller/dashboard')
      else navigate('/admin')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Registration failed. Please try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <div className="auth-header">
          <Link to="/" className="auth-logo">Trust<span>Grid</span></Link>
          <h1 className="auth-title">Create your account</h1>
          <p className="auth-subtitle">Join TrustGrid and start building trust</p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="name">Full Name</label>
            <input
              id="name" name="name" type="text"
              className="form-input" placeholder="Jane Doe"
              value={form.name} onChange={handleChange} required
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="email">Email</label>
            <input
              id="email" name="email" type="email"
              className="form-input" placeholder="you@example.com"
              value={form.email} onChange={handleChange}
              required autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <input
              id="password" name="password" type="password"
              className="form-input" placeholder="At least 8 characters"
              value={form.password} onChange={handleChange}
              required minLength={8} autoComplete="new-password"
            />
          </div>

          <div className="form-group">
            <label className="form-label">I want to</label>
            <div className="role-selector">
              {['buyer', 'seller'].map((r) => (
                <label key={r} className={`role-option ${form.role === r ? 'selected' : ''}`}>
                  <input
                    type="radio" name="role" value={r}
                    checked={form.role === r} onChange={handleChange}
                    style={{ display: 'none' }}
                  />
                  <span className="role-icon">{r === 'buyer' ? '🛍️' : '🏪'}</span>
                  <span className="role-label">{r === 'buyer' ? 'Buy products' : 'Sell products'}</span>
                </label>
              ))}
            </div>
          </div>

          {error && <p className="form-error">{error}</p>}

          <button type="submit" className="btn btn-primary btn-lg auth-submit" disabled={loading}>
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
