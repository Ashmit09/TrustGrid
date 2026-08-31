import React, { useEffect, useState } from 'react'
import SellerLayout from '../../layouts/SellerLayout'
import { orderService } from '../../services/marketplaceService'
import '../buyer/BuyerDashboard.css'
import '../buyer/Orders.css'

export default function SellerOrders() {
  const [orders, setOrders]   = useState([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg]         = useState(null)
  const [acting, setActing]   = useState(false)

  const load = () => orderService.list().then(setOrders).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const ship = async (orderId) => {
    setActing(true); setMsg(null)
    try {
      await orderService.ship(orderId)
      setMsg({ success: true, text: 'Order marked as shipped.' })
      load()
    } catch (e) {
      setMsg({ success: false, text: e.response?.data?.detail || 'Failed.' })
    } finally { setActing(false) }
  }

  const cancel = async (orderId) => {
    setActing(true); setMsg(null)
    try {
      await orderService.cancel(orderId)
      setMsg({ success: true, text: 'Order cancelled.' })
      load()
    } catch (e) {
      setMsg({ success: false, text: e.response?.data?.detail || 'Failed.' })
    } finally { setActing(false) }
  }

  return (
    <SellerLayout>
      <div className="dashboard-header">
        <h1 className="page-title">Orders</h1>
      </div>

      {msg && (
        <div className={`callout-box ${msg.success ? 'callout-success' : 'callout-error'}`}>{msg.text}</div>
      )}

      {loading ? <div className="empty-state">Loading…</div>
       : orders.length === 0 ? <div className="empty-state">No orders yet.</div>
       : (
        <div className="card" style={{ padding: 0 }}>
          {orders.map(o => (
            <div className="order-detail-row" key={o.order_id}>
              <div className="order-detail-row__left">
                <div className="order-detail-row__id">{o.order_id}</div>
                <div className="order-detail-row__meta">
                  Qty {o.quantity} · ₹{Number(o.total_amount).toFixed(2)} · {new Date(o.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="order-detail-row__right">
                <span className={`status-badge status-${o.status}`}>{o.status}</span>
                {o.status === 'paid' && (
                  <>
                    <button className="btn btn-primary btn-sm" onClick={() => ship(o.order_id)} disabled={acting}>Ship</button>
                    <button className="btn btn-danger btn-sm"  onClick={() => cancel(o.order_id)} disabled={acting}>Cancel</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
       )}
    </SellerLayout>
  )
}
