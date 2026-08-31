/**
 * Shared utility helpers for TrustGrid frontend.
 */

/**
 * Returns a human-readable relative time string (e.g. "3d ago", "just now").
 */
export function timeAgo(iso) {
  if (!iso) return ''
  const diff  = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60_000)
  const hours = Math.floor(diff / 3_600_000)
  const days  = Math.floor(diff / 86_400_000)
  if (days > 0)  return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (mins > 0)  return `${mins}m ago`
  return 'just now'
}

/**
 * Format a number as Indian Rupee currency string.
 * e.g. formatINR(1234.5) → "₹1,234.50"
 */
export function formatINR(amount) {
  return `₹${Number(amount).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/**
 * Returns a human-readable label for a score change.
 * e.g. formatChange(18) → "+18"
 */
export function formatChange(change) {
  if (change > 0) return `+${change}`
  return String(change)
}

/**
 * Returns the tier color CSS variable name for a given tier.
 */
export function tierColor(tier) {
  const map = {
    ELITE:      'var(--tier-elite)',
    TRUSTED:    'var(--tier-trusted)',
    STANDARD:   'var(--tier-standard)',
    RESTRICTED: 'var(--tier-restricted)',
  }
  return map[tier] || 'var(--color-primary)'
}

/**
 * Clamp a number between min and max.
 */
export function clamp(val, min, max) {
  return Math.min(max, Math.max(min, val))
}
