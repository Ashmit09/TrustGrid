import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import BuyerLayout from '../../layouts/BuyerLayout'
import { productService, orderService } from '../../services/marketplaceService'
import './BuyerDashboard.css'

export default function ProductDetail() {
  const { id }    = useParams()
  const navigate  = useNavigate()
  const [product, setProduct] = useState(null)
  const [qty, setQty]         = useState(1)
  const [placing, setPlacing] = useState(false)
  const [result, setResult]   = useState(null)   // { success, message, order }
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    productService.get(id)
      .then(setProduct)
      .catch(() => navigate('/buyer/products'))
      .finally(() => setLoading(false))
  }, [id])

  const handleBuy = async () => {
    setPlacing(true)
    setResult(null)
    try {
      const order = await orderService.place({ product_id: product.id, quantity: qty })
      if (order.status === 'paid') {
        setResult({ success: true, message: `Order placed! Payment successful. Order ID: ${order.order_id}`, order })
      } else {
        setResult({ success: false, message: `Payment failed. Order ${order.order_id} was cancelled.`, order })
      }
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || 'Failed to place order.' })
    } finally {
      setPlacing(false)
    }
  }

  if (loading) return <BuyerLayout><div className="empty-state">Loading…</div></BuyerLayout>
  if (!product) return null

  return (
    <BuyerLayout>
      <Link to="/buyer/products" className="btn btn-ghost btn-sm" style={{ alignSelf: 'flex-start' }}>← Back</Link>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'start' }}>
        {/* Product image */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ height: 320, background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 80 }}>
            {product.image_url
              ? <img src={product.image_url} alt={product.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : '📦'
            }
          </div>
        </div>

        {/* Product info + buy */}
        <div className="card" style={{ padding: 28 }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{product.category || 'General'}</div>
          <h1 style={{ fontSize: 22, fontWeight: 800, marginBottom: 12 }}>{product.title}</h1>
          <p style={{ color: 'var(--text-muted)', marginBottom: 20, lineHeight: 1.6 }}>{product.description || 'No description provided.'}</p>

          <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--color-primary)', marginBottom: 16 }}>
            ₹{Number(product.price).toFixed(2)}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
            {product.stock > 0 ? `${product.stock} in stock` : <span style={{ color: 'var(--error)' }}>Out of stock</span>}
          </div>

          {product.stock > 0 && (
            <>
              <div className="form-group" style={{ marginBottom: 16 }}>
                <label className="form-label">Quantity</label>
                <input
                  type="number" min={1} max={Math.min(product.stock, 100)}
                  value={qty} onChange={e => setQty(Number(e.target.value))}
                  className="form-input" style={{ width: 100 }}
                />
              </div>
              <button
                className="btn btn-primary btn-lg"
                onClick={handleBuy}
                disabled={placing}
                style={{ width: '100%' }}
              >
                {placing ? 'Processing…' : 'Buy Now (Simulated Payment)'}
              </button>
            </>
          )}

          {result && (
            <div className={`callout-box ${result.success ? 'callout-success' : 'callout-error'}`} style={{ marginTop: 16 }}>
              <p>{result.message}</p>
              {result.order && (
                <Link to="/buyer/orders" className="btn btn-sm" style={{ marginTop: 8, background: 'rgba(0,0,0,0.07)' }}>
                  View Orders →
                </Link>
              )}
            </div>
          )}
        </div>
      </div>
    </BuyerLayout>
  )
}
