/**
 * Marketplace service — wraps /products and /orders API calls.
 */
import api from './api'

export const productService = {
  list:   (params) => api.get('/products', { params }).then((r) => r.data),
  listMy: ()       => api.get('/products/my').then((r) => r.data),
  get:    (id)     => api.get(`/products/${id}`).then((r) => r.data),
  create: (data)   => api.post('/products', data).then((r) => r.data),
  update: (id, data) => api.put(`/products/${id}`, data).then((r) => r.data),
}

export const orderService = {
  list:     ()          => api.get('/orders').then((r) => r.data),
  get:      (id)        => api.get(`/orders/${id}`).then((r) => r.data),
  place:    (data)      => api.post('/orders', data).then((r) => r.data),
  cancel:   (id)        => api.post(`/orders/${id}/cancel`).then((r) => r.data),
  ship:     (id)        => api.post(`/orders/${id}/ship`).then((r) => r.data),
  complete: (id)        => api.post(`/orders/${id}/complete`).then((r) => r.data),
  requestReturn: (id, data) => api.post(`/orders/${id}/return`, data).then((r) => r.data),
  submitReview:  (id, data) => api.post(`/orders/${id}/review`, data).then((r) => r.data),
}
