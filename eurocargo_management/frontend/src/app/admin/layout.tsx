'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'

const NAV_ITEMS = [
  { href: '/admin/shipments', label: 'Shipments' },
  { href: '/admin/rates',     label: 'Rates' },
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
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <nav style={{
        width: 192,
        background: 'var(--bg-sunken)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        padding: `var(--space-6) 0`,
      }}>
        {/* Wordmark */}
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 17,
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          color: 'var(--text)',
          padding: `0 var(--space-4) var(--space-6)`,
          borderBottom: `1px solid var(--border)`,
        }}>
          Eurocargo
        </div>

        {/* Nav links */}
        <ul style={{ listStyle: 'none', padding: `var(--space-3) 0`, flex: 1 }}>
          {NAV_ITEMS.map(({ href, label }) => {
            const active = pathname.startsWith(href)
            return (
              <li key={href}>
                <Link
                  href={href}
                  style={{
                    display: 'block',
                    padding: `var(--space-2) var(--space-4)`,
                    fontFamily: 'var(--font-display)',
                    fontSize: 14,
                    fontWeight: active ? 600 : 400,
                    letterSpacing: '0.02em',
                    color: active ? 'var(--accent)' : 'var(--text-2)',
                    background: active ? 'var(--accent-dim)' : 'transparent',
                    textDecoration: 'none',
                    borderRadius: 4,
                    margin: `2px var(--space-2)`,
                    transition: 'background 0.1s, color 0.1s',
                  }}
                >
                  {label}
                </Link>
              </li>
            )
          })}
        </ul>

        {/* Logout */}
        <div style={{ padding: `0 var(--space-2) var(--space-2)` }}>
          <button
            onClick={handleLogout}
            style={{
              width: '100%',
              background: 'none',
              border: `1px solid var(--border)`,
              borderRadius: 4,
              color: 'var(--text-3)',
              padding: `var(--space-2) 0`,
              fontSize: 12,
              fontFamily: 'var(--font-display)',
              letterSpacing: '0.03em',
              cursor: 'pointer',
              transition: 'border-color 0.1s, color 0.1s',
            }}
            onMouseEnter={e => {
              const b = e.currentTarget
              b.style.borderColor = 'var(--text-3)'
              b.style.color = 'var(--text-2)'
            }}
            onMouseLeave={e => {
              const b = e.currentTarget
              b.style.borderColor = 'var(--border)'
              b.style.color = 'var(--text-3)'
            }}
          >
            Log out
          </button>
        </div>
      </nav>

      {/* Main content area */}
      <main style={{ flex: 1, overflow: 'auto', background: 'var(--bg)' }}>
        {children}
      </main>
    </div>
  )
}
