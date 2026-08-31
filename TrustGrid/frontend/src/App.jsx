import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

// Common
import ProtectedRoute from './components/common/ProtectedRoute'

// Public pages
import Home       from './pages/public/Home.jsx'
import Login      from './pages/public/Login.jsx'
import Register   from './pages/public/Register.jsx'
import About      from './pages/public/About.jsx'
import NotFound   from './pages/public/NotFound.jsx'

// Buyer pages
import BuyerDashboard  from './pages/buyer/BuyerDashboard.jsx'
import Products        from './pages/buyer/Products.jsx'
import ProductDetail   from './pages/buyer/ProductDetail.jsx'
import BuyerOrders     from './pages/buyer/BuyerOrders.jsx'
import BuyerTrustGrid  from './pages/buyer/BuyerTrustGrid.jsx'
import BuyerProfile    from './pages/buyer/BuyerProfile.jsx'

// Seller pages
import SellerDashboard from './pages/seller/SellerDashboard.jsx'
import SellerProducts  from './pages/seller/SellerProducts.jsx'
import AddProduct      from './pages/seller/AddProduct.jsx'
import SellerOrders    from './pages/seller/SellerOrders.jsx'
import SellerTrustGrid from './pages/seller/SellerTrustGrid.jsx'
import SellerProfile   from './pages/seller/SellerProfile.jsx'

// Admin pages
import AdminDashboard  from './pages/admin/AdminDashboard.jsx'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ── Public ─────────────────────────────────────── */}
        <Route path="/"         element={<Home />} />
        <Route path="/about"    element={<About />} />
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* ── Buyer ──────────────────────────────────────── */}
        <Route path="/buyer/dashboard"      element={<ProtectedRoute requiredRole="buyer"><BuyerDashboard /></ProtectedRoute>} />
        <Route path="/buyer/products"       element={<ProtectedRoute requiredRole="buyer"><Products /></ProtectedRoute>} />
        <Route path="/buyer/products/:id"   element={<ProtectedRoute requiredRole="buyer"><ProductDetail /></ProtectedRoute>} />
        <Route path="/buyer/orders"         element={<ProtectedRoute requiredRole="buyer"><BuyerOrders /></ProtectedRoute>} />
        <Route path="/buyer/trustgrid"      element={<ProtectedRoute requiredRole="buyer"><BuyerTrustGrid /></ProtectedRoute>} />
        <Route path="/buyer/profile"        element={<ProtectedRoute requiredRole="buyer"><BuyerProfile /></ProtectedRoute>} />

        {/* ── Seller ─────────────────────────────────────── */}
        <Route path="/seller/dashboard"     element={<ProtectedRoute requiredRole="seller"><SellerDashboard /></ProtectedRoute>} />
        <Route path="/seller/products"      element={<ProtectedRoute requiredRole="seller"><SellerProducts /></ProtectedRoute>} />
        <Route path="/seller/products/add"  element={<ProtectedRoute requiredRole="seller"><AddProduct /></ProtectedRoute>} />
        <Route path="/seller/orders"        element={<ProtectedRoute requiredRole="seller"><SellerOrders /></ProtectedRoute>} />
        <Route path="/seller/trustgrid"     element={<ProtectedRoute requiredRole="seller"><SellerTrustGrid /></ProtectedRoute>} />
        <Route path="/seller/profile"       element={<ProtectedRoute requiredRole="seller"><SellerProfile /></ProtectedRoute>} />

        {/* ── Admin ───────────────────────────────────────── */}
        <Route path="/admin"                element={<ProtectedRoute requiredRole="admin"><AdminDashboard /></ProtectedRoute>} />

        {/* ── Fallback ────────────────────────────────────── */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
