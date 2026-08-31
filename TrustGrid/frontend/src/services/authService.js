/**
 * Auth service — wraps /auth/* API calls.
 * Stores the JWT and user object in localStorage.
 */
import api from './api'

export const authService = {
  /**
   * Register a new buyer or seller.
   * @param {{ name, email, password, role }} data
   */
  register: async (data) => {
    const res = await api.post('/auth/register', data)
    authService._persist(res.data)
    return res.data
  },

  /**
   * Log in with email + password.
   * @param {{ email, password }} data
   */
  login: async (data) => {
    const res = await api.post('/auth/login', data)
    authService._persist(res.data)
    return res.data
  },

  /** Fetch the currently authenticated user's profile. */
  me: async () => {
    const res = await api.get('/auth/me')
    return res.data
  },

  /** Remove stored credentials (logout). */
  logout: () => {
    localStorage.removeItem('tg_token')
    localStorage.removeItem('tg_user')
  },

  /** Retrieve the stored user object synchronously. */
  getUser: () => {
    try {
      return JSON.parse(localStorage.getItem('tg_user'))
    } catch {
      return null
    }
  },

  /** Returns true if a token is present. */
  isLoggedIn: () => !!localStorage.getItem('tg_token'),

  /** @private */
  _persist: (data) => {
    if (data.access_token) localStorage.setItem('tg_token', data.access_token)
    if (data.user)         localStorage.setItem('tg_user', JSON.stringify(data.user))
  },
}
