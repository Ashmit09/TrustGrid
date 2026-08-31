import React from 'react'
import Navbar from '../components/common/Navbar'
import './Layout.css'

export default function BuyerLayout({ children }) {
  return (
    <div className="layout">
      <Navbar role="buyer" />
      <main className="layout__main">
        <div className="container layout__content">
          {children}
        </div>
      </main>
    </div>
  )
}
