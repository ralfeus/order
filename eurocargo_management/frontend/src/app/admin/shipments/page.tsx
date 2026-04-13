'use client'

import { useEffect, useState, useCallback, useRef, KeyboardEvent } from 'react'
import { useRouter } from 'next/navigation'
import { getApiUrl } from '@/lib/env'
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
  paid: boolean
  created_at: string
  attachments: Attachment[]
}

const STATUS_OPTIONS = ['incoming', 'at_warehouse', 'customs_cleared', 'shipped'] as const
type Status = typeof STATUS_OPTIONS[number]

const STATUS_LABELS: Record<Status, string> = {
  incoming:        'Incoming',
  at_warehouse:    'At warehouse',
  customs_cleared: 'Customs cleared',
  shipped:         'Shipped',
}

const STATUS_COLOURS: Record<Status, string> = {
  incoming:        '#d97706',
  at_warehouse:    '#2563eb',
  customs_cleared: '#7c3aed',
  shipped:         '#16a34a',
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
// Paid toggle with confirmation
// ---------------------------------------------------------------------------
function PaidToggle({
  shipmentId,
  paid,
  onToggle,
}: {
  shipmentId: number
  paid: boolean
  onToggle: (id: number, paid: boolean) => Promise<void>
}) {
  const [busy, setBusy] = useState(false)

  async function handleClick() {
    const next = !paid
    const msg = next
      ? 'Mark this shipment as PAID?'
      : 'Mark this shipment as UNPAID?\nThis will remove the paid status.'
    if (!window.confirm(msg)) return
    setBusy(true)
    try {
      await onToggle(shipmentId, next)
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={busy}
      title={paid ? 'Click to mark as unpaid' : 'Click to mark as paid'}
      style={{
        background: paid ? '#16a34a' : '#9ca3af',
        color: '#fff',
        border: 'none',
        borderRadius: 12,
        padding: '3px 12px',
        fontSize: 12,
        fontWeight: 600,
        cursor: busy ? 'not-allowed' : 'pointer',
        opacity: busy ? 0.7 : 1,
        whiteSpace: 'nowrap',
      }}
    >
      {paid ? '✓ Paid' : 'Unpaid'}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Create-consignment button (DHL label generation)
// ---------------------------------------------------------------------------
function ConsignmentButton({
  shipment,
  onSuccess,
}: {
  shipment: Shipment
  onSuccess: (updated: Shipment) => void
}) {
  const apiUrl = getApiUrl()
  const [busy, setBusy] = useState(false)

  function authHeaders(): Record<string, string> {
    const token = getCookie('admin_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  async function create(force = false) {
    setBusy(true)
    try {
      const res = await fetch(
        `${apiUrl}/api/v1/admin/shipments/${shipment.id}/consignment`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ force }),
        },
      )

      if (res.status === 409) {
        const data = await res.json().catch(() => ({}))
        const confirmed = window.confirm(
          `${data.detail ?? 'Shipment already has a consignment.'}\n\nOverwrite and create a new consignment?`,
        )
        if (confirmed) await create(true)
        return
      }

      if (res.status === 501) {
        const data = await res.json().catch(() => ({}))
        alert(data.detail ?? 'This carrier does not support consignment creation.')
        return
      }

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        alert(`Failed to create consignment: ${data.detail ?? res.statusText}`)
        return
      }

      const updated: Shipment = await res.json()
      onSuccess(updated)
    } catch {
      alert('Network error — could not create consignment.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      onClick={() => create(false)}
      disabled={busy}
      title="Create carrier consignment (generates DHL label)"
      style={{
        background: busy ? '#9ca3af' : '#1d4ed8',
        color: '#fff',
        border: 'none',
        borderRadius: 6,
        padding: '3px 10px',
        fontSize: 12,
        fontWeight: 600,
        cursor: busy ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {busy ? '…' : '+ Label'}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AdminShipmentsPage() {
  const router = useRouter()
  const apiUrl = getApiUrl()

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

  async function handlePaidToggle(shipmentId: number, paid: boolean) {
    const res = await fetch(`${apiUrl}/api/v1/admin/shipments/${shipmentId}/paid`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ paid }),
    })
    if (!res.ok) throw new Error('Failed to update paid status')
    const updated: Shipment = await res.json()
    setShipments(prev => prev.map(s => s.id === shipmentId ? updated : s))
  }

  function handleConsignmentCreated(updated: Shipment) {
    setShipments(prev => prev.map(s => s.id === updated.id ? updated : s))
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

  if (loading) return <main style={mainStyle}><p>Loading…</p></main>
  if (error)   return <main style={mainStyle}><p style={{ color: '#dc2626' }}>{error}</p></main>

  return (
    <main style={mainStyle}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>All Shipments</h1>
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
              <Th>Payment</Th>
              <Th>Tracking</Th>
              <Th>Consignment</Th>
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
                        {STATUS_LABELS[opt]}
                      </option>
                    ))}
                  </select>
                </Td>
                <Td>
                  <PaidToggle
                    shipmentId={s.id}
                    paid={s.paid}
                    onToggle={handlePaidToggle}
                  />
                </Td>
                <Td>
                  <TrackingCell
                    shipmentId={s.id}
                    value={s.tracking_code}
                    onSave={handleTrackingChange}
                  />
                </Td>
                <Td>
                  <ConsignmentButton
                    shipment={s}
                    onSuccess={handleConsignmentCreated}
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
  maxWidth: 1300,
  margin: '32px auto',
  fontFamily: 'sans-serif',
  padding: '0 16px',
}

