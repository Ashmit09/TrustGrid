/**
 * Axios instance pre-configured for the TrustGrid API.
 * The JWT token is attached automatically from localStorage.
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',          // Vite proxies /api → http://127.0.0.1:8000
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor — attach Bearer token ─────────────
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('tg_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── Response interceptor — handle 401 globally ───────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('tg_token')
      localStorage.removeItem('tg_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
