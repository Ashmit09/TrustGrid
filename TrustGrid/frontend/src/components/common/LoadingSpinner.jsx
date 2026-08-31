/**
 * LoadingSpinner — shared loading state component.
 * Used throughout buyer, seller, and admin pages.
 */
import React from 'react'
import './LoadingSpinner.css'

export default function LoadingSpinner({ message = 'Loading…', fullPage = false }) {
  const content = (
    <div className="spinner-container">
      <div className="spinner" />
      {message && <p className="spinner-message">{message}</p>}
    </div>
  )

  if (fullPage) {
    return <div className="spinner-fullpage">{content}</div>
  }

  return content
}
