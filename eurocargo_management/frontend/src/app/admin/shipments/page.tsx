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
  shipment_type: ShipmentType | null
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

const STATUS_STYLE: Record<Status, { bg: string; color: string }> = {
  incoming:        { bg: 'var(--status-incoming-bg)',  color: 'var(--status-incoming-text)' },
  at_warehouse:    { bg: 'var(--status-warehouse-bg)', color: 'var(--status-warehouse-text)' },
  customs_cleared: { bg: 'var(--status-customs-bg)',   color: 'var(--status-customs-text)' },
  shipped:         { bg: 'var(--status-shipped-bg)',   color: 'var(--status-shipped-text)' },
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
          width: 148,
          fontSize: 12,
          padding: '3px 6px',
          opacity: saving ? 0.6 : 1,
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
        borderRadius: 3,
        fontSize: 12,
        color: value ? 'var(--text)' : 'var(--text-3)',
        border: '1px solid transparent',
        transition: 'border-color 0.1s',
      }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'transparent' }}
    >
      {value ?? '—'}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Paid toggle
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
        background: paid ? 'var(--paid-bg)' : 'var(--unpaid-bg)',
        color: paid ? 'var(--paid-text)' : 'var(--unpaid-text)',
        border: `1px solid ${paid ? 'oklch(0.80 0.08 155)' : 'var(--border)'}`,
        borderRadius: 3,
        padding: '2px 10px',
        fontSize: 11,
        fontFamily: 'var(--font-display)',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        cursor: busy ? 'not-allowed' : 'pointer',
        opacity: busy ? 0.6 : 1,
        whiteSpace: 'nowrap',
        transition: 'opacity 0.1s',
      }}
    >
      {paid ? 'Paid' : 'Unpaid'}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Consignment button
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
        background: busy ? 'var(--bg-sunken)' : 'var(--accent)',
        color: busy ? 'var(--text-3)' : 'var(--text-inv)',
        border: 'none',
        borderRadius: 3,
        padding: '3px 10px',
        fontSize: 11,
        fontFamily: 'var(--font-display)',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        cursor: busy ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => { if (!busy) e.currentTarget.style.background = 'var(--accent-hover)' }}
      onMouseLeave={e => { if (!busy) e.currentTarget.style.background = 'var(--accent)' }}
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

  if (loading) return (
    <div style={{ padding: 'var(--space-8)', color: 'var(--text-3)', fontFamily: 'var(--font-display)', letterSpacing: '0.03em' }}>
      Loading…
    </div>
  )

  if (error) return (
    <div style={{ padding: 'var(--space-8)', color: 'var(--danger)' }}>
      {error}
    </div>
  )

  return (
    <div style={{ padding: 'var(--space-6) var(--space-8)' }}>
      {/* Page header */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: '0.02em',
          color: 'var(--text)',
        }}>
          Shipments
        </h1>
        {shipments.length > 0 && (
          <p style={{ marginTop: 'var(--space-1)', fontSize: 12, color: 'var(--text-3)' }}>
            {shipments.length} total
          </p>
        )}
      </div>

      {shipments.length === 0 ? (
        <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No shipments yet.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--bg-sunken)' }}>
                {['Order ID', 'Recipient', 'Carrier', 'Country', 'kg', '€', 'Status', 'Payment', 'Tracking', 'Label', 'Files', 'Created'].map(col => (
                  <th key={col} style={{
                    padding: '7px 10px',
                    fontFamily: 'var(--font-display)',
                    fontWeight: 600,
                    fontSize: 11,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    color: 'var(--text-2)',
                    textAlign: col === 'kg' || col === '€' ? 'right' : 'left',
                    whiteSpace: 'nowrap',
                    borderBottom: '1px solid var(--border)',
                  }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shipments.map((s, i) => {
                const statusStyle = STATUS_STYLE[s.status as Status] ?? { bg: 'var(--bg-sunken)', color: 'var(--text-2)' }
                return (
                  <tr
                    key={s.id}
                    style={{
                      background: i % 2 === 0 ? 'var(--bg)' : 'var(--bg-raised)',
                      borderBottom: '1px solid var(--border)',
                    }}
                  >
                    {/* Order ID */}
                    <td style={tdStyle}>
                      <a
                        href={`/shipments/${s.token}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 500 }}
                        onMouseEnter={e => { e.currentTarget.style.textDecoration = 'underline' }}
                        onMouseLeave={e => { e.currentTarget.style.textDecoration = 'none' }}
                      >
                        {s.order_id}
                      </a>
                    </td>

                    {/* Recipient */}
                    <td style={tdStyle}>{s.customer_name}</td>

                    {/* Carrier */}
                    <td style={{ ...tdStyle, color: 'var(--text-2)' }}>{s.shipment_type?.code ?? '—'}</td>

                    {/* Country */}
                    <td style={{ ...tdStyle, color: 'var(--text-2)' }}>{s.country}</td>

                    {/* Weight */}
                    <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {Number(s.weight_kg).toFixed(3)}
                    </td>

                    {/* Amount */}
                    <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {s.amount_eur != null ? `€${Number(s.amount_eur).toFixed(2)}` : <span style={{ color: 'var(--text-3)' }}>—</span>}
                    </td>

                    {/* Status */}
                    <td style={tdStyle}>
                      <div style={{ position: 'relative', display: 'inline-block' }}>
                        <select
                          value={s.status}
                          disabled={updatingId === s.id}
                          onChange={e => handleStatusChange(s.id, e.target.value as Status)}
                          style={{
                            appearance: 'none',
                            WebkitAppearance: 'none',
                            background: statusStyle.bg,
                            color: statusStyle.color,
                            border: 'none',
                            borderRadius: 3,
                            padding: '2px 20px 2px 8px',
                            fontSize: 11,
                            fontFamily: 'var(--font-display)',
                            fontWeight: 600,
                            letterSpacing: '0.04em',
                            cursor: updatingId === s.id ? 'not-allowed' : 'pointer',
                            opacity: updatingId === s.id ? 0.6 : 1,
                            outline: 'none',
                          }}
                        >
                          {STATUS_OPTIONS.map(opt => (
                            <option key={opt} value={opt}>
                              {STATUS_LABELS[opt]}
                            </option>
                          ))}
                        </select>
                        {/* Custom dropdown arrow */}
                        <span style={{
                          position: 'absolute',
                          right: 5,
                          top: '50%',
                          transform: 'translateY(-50%)',
                          pointerEvents: 'none',
                          fontSize: 8,
                          color: statusStyle.color,
                          lineHeight: 1,
                        }}>▾</span>
                      </div>
                    </td>

                    {/* Payment */}
                    <td style={tdStyle}>
                      <PaidToggle
                        shipmentId={s.id}
                        paid={s.paid}
                        onToggle={handlePaidToggle}
                      />
                    </td>

                    {/* Tracking */}
                    <td style={tdStyle}>
                      <TrackingCell
                        shipmentId={s.id}
                        value={s.tracking_code}
                        onSave={handleTrackingChange}
                      />
                    </td>

                    {/* Consignment */}
                    <td style={tdStyle}>
                      <ConsignmentButton
                        shipment={s}
                        onSuccess={handleConsignmentCreated}
                      />
                    </td>

                    {/* Files */}
                    <td style={tdStyle}>
                      <AttachmentIcon
                        token={s.token}
                        attachments={s.attachments}
                        apiUrl={apiUrl}
                      />
                    </td>

                    {/* Created */}
                    <td style={{ ...tdStyle, color: 'var(--text-3)' }}>
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const tdStyle: React.CSSProperties = {
  padding: '7px 10px',
  verticalAlign: 'middle',
}
