/**
 * ProtectedRoute — redirects unauthenticated users or wrong roles to login.
 */
import React from 'react'
import { Navigate } from 'react-router-dom'
import { authService } from '../../services/authService'

export default function ProtectedRoute({ children, requiredRole }) {
  const user = authService.getUser()

  if (!user || !authService.isLoggedIn()) {
    return <Navigate to="/login" replace />
  }

  if (requiredRole && user.role !== requiredRole) {
    // Redirect to their correct dashboard instead of login
    if (user.role === 'buyer')  return <Navigate to="/buyer/dashboard"  replace />
    if (user.role === 'seller') return <Navigate to="/seller/dashboard" replace />
    return <Navigate to="/login" replace />
  }

  return children
}
