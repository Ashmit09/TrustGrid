import React, { useEffect, useState } from 'react'
import SellerLayout from '../../layouts/SellerLayout'
import { useAuth } from '../../hooks/useAuth'
import { orderService, productService } from '../../services/marketplaceService'
import { Link } from 'react-router-dom'
import '../buyer/BuyerDashboard.css'
import '../buyer/Orders.css'

export default function SellerDashboard() {
  const { user }     = useAuth()
  const [orders, setOrders]   = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      orderService.list().catch(() => []),
      productService.list({ search: undefined }).catch(() => []),
    ]).then(([o, p]) => {
      setOrders(o)
      setProducts(p.filter(pr => pr.seller_id === user?.user_id))
      setLoading(false)
    })
  }, [])

  const pendingOrders = orders.filter(o => o.status === 'paid')
  const shippedOrders = orders.filter(o => o.status === 'shipped')

  return (
    <SellerLayout>
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">Seller Dashboard</h1>
          <p className="page-subtitle">Welcome, {user?.name?.split(' ')[0]}</p>
        </div>
        <Link to="/seller/products/add" className="btn btn-primary">+ Add Product</Link>
      </div>

      <div className="stats-row">
        <div className="stat-card card">
          <span className="stat-card__value">{products.length}</span>
          <span className="stat-card__label">Products Listed</span>
        </div>
        <div className="stat-card card">
          <span className="stat-card__value">{pendingOrders.length}</span>
          <span className="stat-card__label">Pending Orders</span>
        </div>
        <div className="stat-card card">
          <span className="stat-card__value">{shippedOrders.length}</span>
          <span className="stat-card__label">Shipped</span>
        </div>
        <div className="stat-card card">
          <span className="stat-card__value">{user?.user_id}</span>
          <span className="stat-card__label">Your ID</span>
        </div>
      </div>

      <div className="card section-card">
        <div className="section-card__header">
          <h2>Recent Orders</h2>
          <Link to="/seller/orders" className="btn btn-ghost btn-sm">View all →</Link>
        </div>
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : orders.length === 0 ? (
          <div className="empty-state">No orders yet. <Link to="/seller/products/add">List a product</Link> to get started.</div>
        ) : (
          <div className="order-list">
            {orders.slice(0, 6).map(o => (
              <div className="order-row" key={o.order_id}>
                <div className="order-row__id">{o.order_id}</div>
                <div className="order-row__amount">₹{Number(o.total_amount).toFixed(2)}</div>
                <span className={`status-badge status-${o.status}`}>{o.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </SellerLayout>
  )
}
