import React, { useEffect, useState } from 'react'
import BuyerLayout from '../../layouts/BuyerLayout'
import { useAuth } from '../../hooks/useAuth'
import { trustService } from '../../services/trustService'
import { orderService } from '../../services/marketplaceService'
import { Link } from 'react-router-dom'
import './BuyerDashboard.css'

export default function BuyerDashboard() {
  const { user }    = useAuth()
  const [trust, setTrust]   = useState(null)
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      trustService.getMyTrust().catch(() => null),
      orderService.list().catch(() => []),
    ]).then(([t, o]) => {
      setTrust(t)
      setOrders(o.slice(0, 5))
      setLoading(false)
    })
  }, [])

  const recentOrders = orders.slice(0, 5)

  return (
    <BuyerLayout>
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">Welcome back, {user?.name?.split(' ')[0]}</h1>
          <p className="page-subtitle">Here's your marketplace overview</p>
        </div>
        <Link to="/buyer/products" className="btn btn-primary">Browse Products</Link>
      </div>

      {/* Trust Score Card */}
      {trust && (
        <div className="trust-summary-card card">
          <div className="trust-summary__score-block">
            <div className="trust-summary__num">{trust.trust_score}</div>
            <div className="trust-summary__denom">/1000</div>
          </div>
          <div className="trust-summary__details">
            <div className="trust-summary__label">Trust Score</div>
            <div className="trust-summary__badges">
              <span className={`tier-badge tier-${trust.tier}`}>{trust.tier}</span>
              <span className={`confidence-badge conf-${trust.confidence}`}>{trust.confidence} CONFIDENCE</span>
            </div>
            <Link to="/buyer/trustgrid" className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}>
              View Full Dashboard →
            </Link>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="stats-row">
        <div className="stat-card card">
          <span className="stat-card__value">{orders.length}</span>
          <span className="stat-card__label">Total Orders</span>
        </div>
        <div className="stat-card card">
          <span className="stat-card__value">
            {orders.filter(o => o.status === 'completed').length}
          </span>
          <span className="stat-card__label">Completed</span>
        </div>
        <div className="stat-card card">
          <span className="stat-card__value">
            {orders.filter(o => o.status === 'paid' || o.status === 'shipped').length}
          </span>
          <span className="stat-card__label">Active</span>
        </div>
        <div className="stat-card card">
          <span className="stat-card__value">{user?.user_id}</span>
          <span className="stat-card__label">Your ID</span>
        </div>
      </div>

      {/* Recent Orders */}
      <div className="card section-card">
        <div className="section-card__header">
          <h2>Recent Orders</h2>
          <Link to="/buyer/orders" className="btn btn-ghost btn-sm">View all →</Link>
        </div>
        {loading ? (
          <p className="empty-state">Loading…</p>
        ) : recentOrders.length === 0 ? (
          <div className="empty-state">
            <p>No orders yet.</p>
            <Link to="/buyer/products" className="btn btn-primary btn-sm" style={{ marginTop: 8 }}>
              Browse Products
            </Link>
          </div>
        ) : (
          <div className="order-list">
            {recentOrders.map(order => (
              <div className="order-row" key={order.order_id}>
                <div className="order-row__id">{order.order_id}</div>
                <div className="order-row__amount">₹{Number(order.total_amount).toFixed(2)}</div>
                <span className={`status-badge status-${order.status}`}>{order.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </BuyerLayout>
  )
}
