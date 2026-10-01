// TrustGrid API client — all axios calls go through here
import axios from "axios";

const BASE_URL = "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Auto-attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("tg_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default api;

// ── Auth ──────────────────────────────────────────────────────────────────────
export const register = (data) => api.post("/auth/register", data);
export const login    = (data) => api.post("/auth/login", data);
export const getMe    = ()     => api.get("/auth/me");

// ── Products ──────────────────────────────────────────────────────────────────
export const listProducts    = ()       => api.get("/products");
export const getProduct      = (id)     => api.get(`/products/${id}`);
export const createProduct   = (data)   => api.post("/products", data);

// ── Orders ────────────────────────────────────────────────────────────────────
export const listOrders      = ()       => api.get("/orders");
export const placeOrder      = (data)   => api.post("/orders", data);
export const cancelOrder     = (id)     => api.post(`/orders/${id}/cancel`);
export const fulfillOrder    = (id)     => api.post(`/orders/${id}/fulfill`);
export const shipOrder       = (id)     => api.post(`/orders/${id}/ship`);
export const deliverOrder    = (id)     => api.post(`/orders/${id}/deliver`);
export const payOrder        = (id, m)  => api.post(`/orders/${id}/pay`, { order_id: id, method: m });
export const requestReturn   = (id, r)  => api.post(`/orders/${id}/return`, { reason: r });
export const submitReview    = (id, d)  => api.post(`/orders/${id}/review`, d);

// ── Trust ─────────────────────────────────────────────────────────────────────
export const getMyTrust      = ()       => api.get("/trust/me");
export const getTrustHistory = (uid)    => api.get(`/trust/${uid}/history`);
export const getTrustBreakdown = (uid)  => api.get(`/trust/${uid}/breakdown`);
export const getTrustBenefits  = (uid)  => api.get(`/trust/${uid}/benefits`);
export const recalculateTrust  = ()     => api.post("/trust/recalculate");

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminAnalytics     = ()    => api.get("/admin/analytics");
export const adminUsers         = ()    => api.get("/admin/users");
export const trustDistribution  = ()    => api.get("/admin/trust-distribution");
