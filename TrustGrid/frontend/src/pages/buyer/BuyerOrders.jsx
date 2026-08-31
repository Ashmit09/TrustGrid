import React, { useEffect, useState } from 'react'
import BuyerLayout from '../../layouts/BuyerLayout'
import { orderService } from '../../services/marketplaceService'
import './BuyerDashboard.css'
import './Orders.css'

const STATUS_ACTIONS = {
  paid:      ['cancel', 'complete_note'],
  shipped:   ['complete', 'return'],
  completed: ['return', 'review'],
}

export default function BuyerOrders() {
  const [orders, setOrders]   = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal]     = useState(null)   // { type, order }
  const [input, setInput]     = useState('')
  const [acting, setActing]   = useState(false)
  const [msg, setMsg]         = useState(null)

  const load = () => orderService.list().then(setOrders).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const act = async (type, order) => {
    setActing(true)
    setMsg(null)
    try {
      if (type === 'cancel')  await orderService.cancel(order.order_id)
      if (type === 'complete') await orderService.complete(order.order_id)
      if (type === 'return')   await orderService.requestReturn(order.order_id, { reason: input })
      if (type === 'review')   await orderService.submitReview(order.order_id, { rating: Number(input) || 5, comment: '' })
      setMsg({ success: true, text: 'Done!' })
      setModal(null)
      load()
    } catch (err) {
      setMsg({ success: false, text: err.response?.data?.detail || 'Action failed.' })
    } finally {
      setActing(false)
    }
  }

  return (
    <BuyerLayout>
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">My Orders</h1>
          <p className="page-subtitle">{orders.length} order{orders.length !== 1 ? 's' : ''} total</p>
        </div>
      </div>

      {msg && (
        <div className={`callout-box ${msg.success ? 'callout-success' : 'callout-error'}`}>
          {msg.text}
        </div>
      )}

      {loading ? (
        <div className="empty-state">Loading orders…</div>
      ) : orders.length === 0 ? (
        <div className="empty-state">No orders yet.</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          {orders.map(order => (
            <div className="order-detail-row" key={order.order_id}>
              <div className="order-detail-row__left">
                <div className="order-detail-row__id">{order.order_id}</div>
                <div className="order-detail-row__meta">
                  Qty {order.quantity} · ₹{Number(order.total_amount).toFixed(2)} ·{' '}
                  {new Date(order.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="order-detail-row__right">
                <span className={`status-badge status-${order.status}`}>{order.status}</span>
                <div className="order-actions">
                  {order.status === 'paid' && (
                    <button className="btn btn-danger btn-sm" onClick={() => { setModal({ type: 'cancel', order }); setInput('') }}>
                      Cancel
                    </button>
                  )}
                  {order.status === 'shipped' && (
                    <button className="btn btn-primary btn-sm" onClick={() => act('complete', order)}>
                      Confirm Receipt
                    </button>
                  )}
                  {order.status === 'shipped' && (
                    <button className="btn btn-secondary btn-sm" onClick={() => { setModal({ type: 'return', order }); setInput('') }}>
                      Request Return
                    </button>
                  )}
                  {order.status === 'completed' && (
                    <button className="btn btn-secondary btn-sm" onClick={() => { setModal({ type: 'review', order }); setInput('5') }}>
                      Leave Review
                    </button>
                  )}
                  {order.status === 'completed' && (
                    <button className="btn btn-ghost btn-sm" onClick={() => { setModal({ type: 'return', order }); setInput('') }}>
                      Return
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Action modal */}
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal-box card" onClick={e => e.stopPropagation()}>
            <h3 style={{ marginBottom: 12, fontWeight: 700 }}>
              {modal.type === 'cancel'  && 'Cancel Order'}
              {modal.type === 'return'  && 'Request Return'}
              {modal.type === 'review'  && 'Leave a Review'}
            </h3>
            {modal.type === 'return' && (
              <input className="form-input" placeholder="Reason for return…" value={input} onChange={e => setInput(e.target.value)} />
            )}
            {modal.type === 'review' && (
              <input type="number" min={1} max={5} className="form-input" placeholder="Rating (1-5)" value={input} onChange={e => setInput(e.target.value)} />
            )}
            {msg && !msg.success && <p className="form-error" style={{ marginTop: 8 }}>{msg.text}</p>}
            <div className="form-actions" style={{ marginTop: 16 }}>
              <button className="btn btn-primary" onClick={() => act(modal.type, modal.order)} disabled={acting}>
                {acting ? '…' : 'Confirm'}
              </button>
              <button className="btn btn-ghost" onClick={() => setModal(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </BuyerLayout>
  )
}
