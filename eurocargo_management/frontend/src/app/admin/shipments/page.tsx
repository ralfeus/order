'use client'

import { useEffect, useState, useCallback, useRef, KeyboardEvent } from 'react'
import { useRouter } from 'next/navigation'
import AttachmentIcon from './AttachmentIcon'

interface Attachment {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  uploaded_at: string
}

interface ShipmentType {
  id: number
  code: string
  name: string
}

interface Shipment {
  id: number
  token: string
  order_id: string
  customer_name: string
  email: string
  country: string
  shipment_type: ShipmentType
  weight_kg: string
  amount_eur: string | null
  tracking_code: string | null
  status: string
  created_at: string
  attachments: Attachment[]
}

const STATUS_OPTIONS = ['pending', 'paid', 'shipped'] as const
type Status = typeof STATUS_OPTIONS[number]

const STATUS_COLOURS: Record<Status, string> = {
  pending: '#d97706',
  paid: '#16a34a',
  shipped: '#1d4ed8',
}

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : ''
}

// ---------------------------------------------------------------------------
// Inline-editable tracking code cell
// ---------------------------------------------------------------------------
function TrackingCell({
  shipmentId,
  value,
  onSave,
}: {
  shipmentId: number
  value: string | null
  onSave: (id: number, code: string | null) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) inputRef.current?.select()
  }, [editing])

  function startEdit() {
    setDraft(value ?? '')
    setEditing(true)
  }

  async function commit() {
    const newCode = draft.trim() || null
    if (newCode === value) { setEditing(false); return }
    setSaving(true)
    try {
      await onSave(shipmentId, newCode)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') { e.preventDefault(); commit() }
    if (e.key === 'Escape') { setEditing(false) }
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={handleKeyDown}
        disabled={saving}
        placeholder="tracking code"
        style={{
          border: '1px solid #93c5fd',
          borderRadius: 4,
          padding: '3px 6px',
          fontSize: 13,
          width: 160,
          outline: 'none',
          background: saving ? '#f3f4f6' : '#fff',
        }}
      />
    )
  }

  return (
    <span
      onClick={startEdit}
      title="Click to edit"
      style={{
        cursor: 'text',
        display: 'inline-block',
        minWidth: 80,
        padding: '3px 6px',
        borderRadius: 4,
        color: value ? '#111' : '#9ca3af',
        border: '1px solid transparent',
      }}
      onMouseEnter={e => (e.currentTarget.style.border = '1px solid #d1d5db')}
      onMouseLeave={e => (e.currentTarget.style.border = '1px solid transparent')}
    >
      {value ?? '—'}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AdminShipmentsPage() {
  const router = useRouter()
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

  const [shipments, setShipments] = useState<Shipment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatingId, setUpdatingId] = useState<number | null>(null)

  const authHeaders = useCallback((): Record<string, string> => {
    const token = getCookie('admin_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [])

  const fetchShipments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/admin/shipments`, {
        headers: authHeaders(),
      })
      if (res.status === 401 || res.status === 403) {
        router.push('/admin/login')
        return
      }
      if (!res.ok) throw new Error('Failed to load shipments')
      setShipments(await res.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [apiUrl, authHeaders, router])

  useEffect(() => { fetchShipments() }, [fetchShipments])

  async function handleStatusChange(shipmentId: number, newStatus: Status) {
    setUpdatingId(shipmentId)
    try {
      const res = await fetch(`${apiUrl}/api/v1/admin/shipments/${shipmentId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ status: newStatus }),
      })
      if (!res.ok) throw new Error('Failed to update status')
      const updated: Shipment = await res.json()
      setShipments(prev => prev.map(s => s.id === shipmentId ? updated : s))
    } catch {
      alert('Could not update status. Please try again.')
    } finally {
      setUpdatingId(null)
    }
  }

  async function handleTrackingChange(shipmentId: number, trackingCode: string | null) {
    const res = await fetch(`${apiUrl}/api/v1/admin/shipments/${shipmentId}/tracking`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ tracking_code: trackingCode }),
    })
    if (!res.ok) throw new Error('Failed to update tracking code')
    const updated: Shipment = await res.json()
    setShipments(prev => prev.map(s => s.id === shipmentId ? updated : s))
  }

  function handleLogout() {
    document.cookie = 'admin_token=; path=/; max-age=0'
    router.push('/admin/login')
  }

  if (loading) return <main style={mainStyle}><p>Loading…</p></main>
  if (error) return <main style={mainStyle}><p style={{ color: '#dc2626' }}>{error}</p></main>

  return (
    <main style={mainStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>All Shipments</h1>
        <button onClick={handleLogout} style={logoutStyle}>Log out</button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f3f4f6', textAlign: 'left' }}>
              <Th>Order ID</Th>
              <Th>Recipient</Th>
              <Th>Carrier</Th>
              <Th>Country</Th>
              <Th>Weight (kg)</Th>
              <Th>Amount (€)</Th>
              <Th>Status</Th>
              <Th>Tracking</Th>
              <Th>Files</Th>
              <Th>Created</Th>
            </tr>
          </thead>
          <tbody>
            {shipments.map(s => (
              <tr key={s.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                <Td>
                  <a
                    href={`/shipments/${s.token}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#1d4ed8', textDecoration: 'none' }}
                  >
                    {s.order_id}
                  </a>
                </Td>
                <Td>{s.customer_name}</Td>
                <Td>{s.shipment_type.code}</Td>
                <Td>{s.country}</Td>
                <Td>{Number(s.weight_kg).toFixed(3)}</Td>
                <Td>{s.amount_eur != null ? `€${Number(s.amount_eur).toFixed(2)}` : '—'}</Td>
                <Td>
                  <select
                    value={s.status}
                    disabled={updatingId === s.id}
                    onChange={e => handleStatusChange(s.id, e.target.value as Status)}
                    style={{
                      background: STATUS_COLOURS[s.status as Status] ?? '#6b7280',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 12,
                      padding: '3px 10px',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {STATUS_OPTIONS.map(opt => (
                      <option key={opt} value={opt} style={{ background: '#fff', color: '#111' }}>
                        {opt}
                      </option>
                    ))}
                  </select>
                </Td>
                <Td>
                  <TrackingCell
                    shipmentId={s.id}
                    value={s.tracking_code}
                    onSave={handleTrackingChange}
                  />
                </Td>
                <Td>
                  <AttachmentIcon
                    token={s.token}
                    attachments={s.attachments}
                    apiUrl={apiUrl}
                  />
                </Td>
                <Td>{new Date(s.created_at).toLocaleDateString()}</Td>
              </tr>
            ))}
          </tbody>
        </table>

        {shipments.length === 0 && (
          <p style={{ textAlign: 'center', color: '#6b7280', marginTop: 32 }}>No shipments yet.</p>
        )}
      </div>
    </main>
  )
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th style={{ padding: '10px 12px', fontWeight: 600, color: '#374151', whiteSpace: 'nowrap' }}>
      {children}
    </th>
  )
}

function Td({ children }: { children: React.ReactNode }) {
  return <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>{children}</td>
}

const mainStyle: React.CSSProperties = {
  maxWidth: 1200,
  margin: '32px auto',
  fontFamily: 'sans-serif',
  padding: '0 16px',
}

const logoutStyle: React.CSSProperties = {
  background: 'none',
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '6px 14px',
  cursor: 'pointer',
  fontSize: 13,
}
