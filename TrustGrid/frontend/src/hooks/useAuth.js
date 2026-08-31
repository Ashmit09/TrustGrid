/**
 * useAuth — reads the stored user from localStorage and provides logout.
 * Phase 4 will add a proper AuthContext; this is sufficient for Phase 3.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authService } from '../services/authService'

export function useAuth() {
  const navigate  = useNavigate()
  const [user, setUser] = useState(() => authService.getUser())

  const logout = () => {
    authService.logout()
    navigate('/login')
  }

  useEffect(() => {
    setUser(authService.getUser())
  }, [])

  return { user, logout, isLoggedIn: !!user }
}
