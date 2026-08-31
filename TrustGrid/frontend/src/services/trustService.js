/**
 * TrustGrid service — wraps all /trust/* API calls.
 */
import api from './api'

export const trustService = {
  /** Full TrustGrid profile (score, tier, confidence, breakdown, benefits, history) */
  getMyTrust:   ()         => api.get('/trust/me').then((r) => r.data),

  /** Score-change history for a user */
  getHistory:   (userId)   => api.get(`/trust/${userId}/history`).then((r) => r.data),

  /** Per-dimension breakdown + recommendations */
  getBreakdown: (userId)   => api.get(`/trust/${userId}/breakdown`).then((r) => r.data),

  /** Active + inactive privileges for a user */
  getBenefits:  (userId)   => api.get(`/trust/${userId}/benefits`).then((r) => r.data),

  /** Human-readable score explanation + driving factors */
  getExplanation: (userId) => api.get(`/trust/${userId}/explain`).then((r) => r.data),

  /** Claim a referral reward */
  claimReferral: (referredEmail) =>
    api.post('/trust/referral', { referred_email: referredEmail }).then((r) => r.data),

  /**
   * What-if simulation — projects score change for hypothetical events.
   * @param {string} userId
   * @param {{ extra_completions, extra_cancellations, extra_returns, extra_payments }} body
   */
  simulate: (userId, body) =>
    api.post(`/trust/${userId}/simulate`, body).then((r) => r.data),
}
