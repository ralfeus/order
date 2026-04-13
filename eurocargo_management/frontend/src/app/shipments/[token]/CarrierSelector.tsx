'use client'

import { useEffect, useState } from 'react'
import { getApiUrl } from '@/lib/env'

interface CarrierOption {
  id: number
  code: string
  name: string
  enabled: boolean
}

interface Props {
  token: string
  currentCarrierCode?: string | null
}

export default function CarrierSelector({ token, currentCarrierCode }: Props) {
  const [carriers, setCarriers] = useState<CarrierOption[]>([])
  const [selected, setSelected] = useState<string>(currentCarrierCode ?? '')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const apiUrl = getApiUrl()
    fetch(`${apiUrl}/api/v1/shipment-types`)
      .then(r => r.json())
      .then((data: CarrierOption[]) => {
        const enabled = data.filter(c => c.enabled)
        setCarriers(enabled)
        // Pre-select current carrier or first available
        if (!selected && enabled.length > 0) {
          setSelected(enabled[0].code)
        }
      })
      .catch(() => setError('Failed to load available carriers'))
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleConfirm() {
    if (!selected) return
    setSaving(true)
    setError(null)
    try {
      const apiUrl = getApiUrl()
      const res = await fetch(`${apiUrl}/api/v1/shipments/${token}/type`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shipment_type_code: selected }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? 'Failed to set carrier')
      }
      // Reload to reflect updated carrier and cost
      window.location.reload()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
      setSaving(false)
    }
  }

  if (loading) {
    return <p style={{ color: '#6b7280', fontSize: 14 }}>Loading available carriers…</p>
  }

  if (carriers.length === 0) {
    return <p style={{ color: '#6b7280', fontSize: 14 }}>No carriers available at this time.</p>
  }

  const changed = selected !== (currentCarrierCode ?? '')

  return (
    <section style={sectionStyle}>
      <h2 style={{ fontSize: 17, marginTop: 0, marginBottom: 12 }}>
        {currentCarrierCode ? 'Change carrier' : 'Select a carrier'}
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
        {carriers.map(c => (
          <label
            key={c.code}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              cursor: 'pointer',
              padding: '10px 14px',
              borderRadius: 6,
              border: selected === c.code ? '2px solid #2563eb' : '2px solid #e5e7eb',
              background: selected === c.code ? '#eff6ff' : '#fff',
              transition: 'border-color 0.15s',
            }}
          >
            <input
              type="radio"
              name="carrier"
              value={c.code}
              checked={selected === c.code}
              onChange={() => setSelected(c.code)}
              style={{ accentColor: '#2563eb' }}
            />
            <span style={{ fontWeight: 500 }}>{c.name}</span>
            <span style={{ color: '#9ca3af', fontSize: 13 }}>({c.code})</span>
          </label>
        ))}
      </div>

      {error && <p style={{ color: '#dc2626', fontSize: 14, marginBottom: 10 }}>{error}</p>}

      <button
        onClick={handleConfirm}
        disabled={saving || !changed}
        style={{
          background: saving || !changed ? '#9ca3af' : '#2563eb',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '10px 24px',
          fontSize: 15,
          fontWeight: 600,
          cursor: saving || !changed ? 'not-allowed' : 'pointer',
          opacity: saving ? 0.8 : 1,
          transition: 'background 0.15s',
        }}
      >
        {saving ? 'Saving…' : currentCarrierCode ? 'Update carrier' : 'Confirm carrier'}
      </button>

      {!changed && currentCarrierCode && (
        <p style={{ marginTop: 8, fontSize: 13, color: '#6b7280' }}>
          Select a different carrier above to change.
        </p>
      )}
    </section>
  )
}

const sectionStyle: React.CSSProperties = {
  background: '#f0fdf4',
  border: '1px solid #bbf7d0',
  borderRadius: 8,
  padding: 20,
  marginBottom: 24,
}
