import React, { useEffect, useState } from 'react'
import BuyerLayout from '../../layouts/BuyerLayout'
import { productService } from '../../services/marketplaceService'
import { Link } from 'react-router-dom'
import './BuyerDashboard.css'

const CATEGORY_ICONS = {
  Electronics: '🔌', Clothing: '👕', Books: '📚',
  Food: '🍎', Home: '🏠', Sports: '⚽', Beauty: '💄',
  default: '📦',
}

export default function Products() {
  const [products, setProducts] = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(true)

  const load = (q = '') => {
    setLoading(true)
    productService.list({ search: q || undefined })
      .then(setProducts)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    load(search)
  }

  return (
    <BuyerLayout>
      <div className="dashboard-header">
        <div>
          <h1 className="page-title">Products</h1>
          <p className="page-subtitle">Browse the marketplace</p>
        </div>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8 }}>
          <input
            className="form-input"
            placeholder="Search products…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 220 }}
          />
          <button type="submit" className="btn btn-primary btn-sm">Search</button>
        </form>
      </div>

      {loading ? (
        <div className="empty-state">Loading products…</div>
      ) : products.length === 0 ? (
        <div className="empty-state">No products found.</div>
      ) : (
        <div className="product-grid">
          {products.map(p => (
            <Link to={`/buyer/products/${p.id}`} key={p.id} style={{ textDecoration: 'none' }}>
              <div className="product-card card">
                <div className="product-card__img">
                  {p.image_url
                    ? <img src={p.image_url} alt={p.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    : <span>{CATEGORY_ICONS[p.category] || CATEGORY_ICONS.default}</span>
                  }
                </div>
                <div className="product-card__body">
                  <div className="product-card__title">{p.title}</div>
                  <div className="product-card__category">{p.category || 'General'}</div>
                  <div className="product-card__footer">
                    <span className="product-card__price">₹{Number(p.price).toFixed(2)}</span>
                    <span className="product-card__stock">{p.stock} in stock</span>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </BuyerLayout>
  )
}
