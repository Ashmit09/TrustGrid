/**
 * Buyer Profile page — shows account info and user ID.
 */
import React from 'react'
import BuyerLayout from '../../layouts/BuyerLayout'
import { useAuth } from '../../hooks/useAuth'
import '../buyer/BuyerDashboard.css'

export default function BuyerProfile() {
  const { user } = useAuth()

  return (
    <BuyerLayout>
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">Your TrustGrid account details</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 560, padding: 32 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* User ID */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)', marginBottom: 6 }}>
              TrustGrid ID
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 20,
              fontWeight: 800,
              color: 'var(--color-primary)',
              background: 'var(--color-primary-light)',
              padding: '10px 16px',
              borderRadius: 'var(--radius)',
              display: 'inline-block',
            }}>
              {user?.user_id}
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
              This is your permanent, unique identifier in TrustGrid.
            </p>
          </div>

          <div className="divider" />

          {/* Name */}
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <div className="form-input" style={{ background: 'var(--bg)', cursor: 'default', color: 'var(--text-muted)' }}>
              {user?.name}
            </div>
          </div>

          {/* Email */}
          <div className="form-group">
            <label className="form-label">Email Address</label>
            <div className="form-input" style={{ background: 'var(--bg)', cursor: 'default', color: 'var(--text-muted)' }}>
              {user?.email}
            </div>
          </div>

          {/* Role */}
          <div className="form-group">
            <label className="form-label">Account Role</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                display: 'inline-block',
                padding: '4px 12px',
                background: 'var(--color-primary-light)',
                color: 'var(--color-primary-dark)',
                borderRadius: 'var(--radius-full)',
                fontSize: 12,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}>
                🛍️ Buyer
              </span>
            </div>
          </div>

          <p style={{ fontSize: 12, color: 'var(--text-light)', fontStyle: 'italic' }}>
            Account details cannot be changed in this demo prototype.
          </p>
        </div>
      </div>
    </BuyerLayout>
  )
}
