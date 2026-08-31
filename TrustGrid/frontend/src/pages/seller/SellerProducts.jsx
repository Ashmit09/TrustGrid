import React, { useEffect, useState } from 'react'
import SellerLayout from '../../layouts/SellerLayout'
import { useAuth } from '../../hooks/useAuth'
import { productService } from '../../services/marketplaceService'
import { Link } from 'react-router-dom'
import '../buyer/BuyerDashboard.css'

export default function SellerProducts() {
  const { user }      = useAuth()
  const [products, setProducts] = useState([])
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    productService.listMy ? productService.listMy().then(setProducts).finally(() => setLoading(false))
      : productService.list().then(all => {
          setProducts(all.filter(p => p.seller_id === user?.user_id))
          setLoading(false)
        })
  }, [])

  return (
    <SellerLayout>
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">My Products</h1>
          <p className="page-subtitle">{products.length} product{products.length !== 1 ? 's' : ''} listed</p>
        </div>
        <Link to="/seller/products/add" className="btn btn-primary">+ Add Product</Link>
      </div>

      {loading ? (
        <div className="empty-state">Loading…</div>
      ) : products.length === 0 ? (
        <div className="empty-state">
          <p>No products yet.</p>
          <Link to="/seller/products/add" className="btn btn-primary btn-sm" style={{ marginTop: 8 }}>Add your first product</Link>
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          {products.map(p => (
            <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{p.title}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{p.category} · {p.stock} in stock</div>
              </div>
              <div style={{ fontWeight: 800, color: 'var(--color-primary)' }}>₹{Number(p.price).toFixed(2)}</div>
              <span className={`status-badge ${p.is_active ? 'status-completed' : 'status-cancelled'}`}>
                {p.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          ))}
        </div>
      )}
    </SellerLayout>
  )
}
