import React from 'react'
import Navbar from '../components/common/Navbar'
import './Layout.css'

export default function SellerLayout({ children }) {
  return (
    <div className="layout">
      <Navbar role="seller" />
      <main className="layout__main">
        <div className="container layout__content">
          {children}
        </div>
      </main>
    </div>
  )
}
