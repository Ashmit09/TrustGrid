/**
 * Shared Navbar component used inside buyer/seller layouts.
 */
import React from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import './Navbar.css'

export default function Navbar({ role }) {
  const { user, logout } = useAuth()

  const buyerLinks = [
    { to: '/buyer/dashboard',  label: 'Dashboard' },
    { to: '/buyer/products',   label: 'Products' },
    { to: '/buyer/orders',     label: 'My Orders' },
    { to: '/buyer/trustgrid',  label: 'TrustGrid' },
    { to: '/buyer/profile',    label: 'Profile' },
  ]

  const sellerLinks = [
    { to: '/seller/dashboard', label: 'Dashboard' },
    { to: '/seller/products',  label: 'My Products' },
    { to: '/seller/orders',    label: 'Orders' },
    { to: '/seller/trustgrid', label: 'TrustGrid' },
    { to: '/seller/profile',   label: 'Profile' },
  ]

  const adminLinks = [
    { to: '/admin', label: 'Analytics' },
  ]

  const links = role === 'seller' ? sellerLinks : role === 'admin' ? adminLinks : buyerLinks

  return (
    <nav className="navbar">
      <div className="navbar__inner">
        <Link to={role === 'seller' ? '/seller/dashboard' : role === 'admin' ? '/admin' : '/buyer/dashboard'} className="navbar__logo">
          Trust<span>Grid</span>
        </Link>

        <div className="navbar__links">
          {links.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `navbar__link ${isActive ? 'active' : ''}`}
            >
              {label}
            </NavLink>
          ))}
        </div>

        <div className="navbar__user">
          <span className="navbar__user-id">{user?.user_id}</span>
          <button className="btn btn-ghost btn-sm" onClick={logout}>Sign Out</button>
        </div>
      </div>
    </nav>
  )
}
