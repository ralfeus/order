'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'

const NAV_ITEMS = [
  { href: '/admin/shipments', label: 'Shipments' },
  { href: '/admin/rates',     label: 'Shipment Rates' },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()

  function handleLogout() {
    document.cookie = 'admin_token=; path=/; max-age=0'
    router.push('/admin/login')
  }

  // Login page uses full-screen layout — no sidebar
  if (pathname === '/admin/login') {
    return <>{children}</>
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', fontFamily: 'sans-serif' }}>
      {/* Sidebar */}
      <nav style={{
        width: 220,
        background: '#1e293b',
        color: '#f1f5f9',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        padding: '24px 0',
      }}>
        <div style={{
          fontSize: 15,
          fontWeight: 700,
          letterSpacing: '0.05em',
          padding: '0 20px 24px',
          borderBottom: '1px solid #334155',
          color: '#94a3b8',
          textTransform: 'uppercase',
        }}>
          Eurocargo
        </div>

        <ul style={{ listStyle: 'none', margin: 0, padding: '16px 0' }}>
          {NAV_ITEMS.map(({ href, label }) => {
            const active = pathname.startsWith(href)
            return (
              <li key={href}>
                <Link
                  href={href}
                  style={{
                    display: 'block',
                    padding: '10px 20px',
                    color: active ? '#f1f5f9' : '#94a3b8',
                    background: active ? '#334155' : 'transparent',
                    textDecoration: 'none',
                    borderLeft: active ? '3px solid #3b82f6' : '3px solid transparent',
                    fontSize: 14,
                    fontWeight: active ? 600 : 400,
                    transition: 'background 0.15s',
                  }}
                >
                  {label}
                </Link>
              </li>
            )
          })}
        </ul>

        {/* Log out pinned to bottom */}
        <div style={{ marginTop: 'auto', padding: '0 12px 16px' }}>
          <button
            onClick={handleLogout}
            style={{
              width: '100%',
              background: 'none',
              border: '1px solid #475569',
              borderRadius: 6,
              color: '#94a3b8',
              padding: '8px 0',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            Log out
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto' }}>
        {children}
      </main>
    </div>
  )
}
