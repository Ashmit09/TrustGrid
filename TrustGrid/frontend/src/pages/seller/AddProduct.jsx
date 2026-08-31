import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import SellerLayout from '../../layouts/SellerLayout'
import { productService } from '../../services/marketplaceService'
import '../buyer/BuyerDashboard.css'

export default function AddProduct() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    title: '', description: '', price: '', stock: '', category: '', image_url: ''
  })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')

  const CATEGORIES = ['Electronics', 'Clothing', 'Books', 'Food', 'Home', 'Sports', 'Beauty', 'Other']

  const handleChange = e => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async e => {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      await productService.create({
        title: form.title,
        description: form.description || undefined,
        price: parseFloat(form.price),
        stock: parseInt(form.stock),
        category: form.category || undefined,
        image_url: form.image_url || undefined,
      })
      navigate('/seller/products')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create product.')
    } finally { setSaving(false) }
  }

  return (
    <SellerLayout>
      <div className="form-page">
        <div className="card">
          <h1>Add New Product</h1>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Title *</label>
              <input name="title" className="form-input" value={form.title} onChange={handleChange} required minLength={2} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea name="description" className="form-input" value={form.description} onChange={handleChange} rows={3} style={{ resize: 'vertical' }} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div className="form-group">
                <label className="form-label">Price (₹) *</label>
                <input name="price" type="number" min="0.01" step="0.01" className="form-input" value={form.price} onChange={handleChange} required />
              </div>
              <div className="form-group">
                <label className="form-label">Stock *</label>
                <input name="stock" type="number" min="0" className="form-input" value={form.stock} onChange={handleChange} required />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Category</label>
              <select name="category" className="form-input" value={form.category} onChange={handleChange}>
                <option value="">Select category…</option>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Image URL (optional)</label>
              <input name="image_url" type="url" className="form-input" value={form.image_url} onChange={handleChange} placeholder="https://…" />
            </div>
            {error && <p className="form-error">{error}</p>}
            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Add Product'}</button>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/seller/products')}>Cancel</button>
            </div>
          </form>
        </div>
      </div>
    </SellerLayout>
  )
}
