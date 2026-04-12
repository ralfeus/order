'use client'

import { useState } from 'react'
import { getApiUrl } from '@/lib/env'

interface Props {
  token: string
  amountEur: string
}

export default function PayButton({ token, amountEur }: Props) {
  const [method, setMethod] = useState<'card' | 'sepa'>('card')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handlePay() {
    setLoading(true)
    setError(null)
    try {
      const apiUrl = getApiUrl()
      const res = await fetch(`${apiUrl}/api/v1/shipments/${token}/payments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? 'Payment initiation failed')
      }
      const data = await res.json()
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      } else {
        setError('No checkout URL returned. Please try again.')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <p style={{ marginBottom: 12, fontWeight: 500 }}>
        Pay <strong>€{Number(amountEur).toFixed(2)}</strong> via:
      </p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        {(['card', 'sepa'] as const).map(m => (
          <label key={m} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input
              type="radio"
              name="method"
              value={m}
              checked={method === m}
              onChange={() => setMethod(m)}
            />
            {m === 'card' ? 'Credit / Debit Card' : 'SEPA Bank Transfer'}
          </label>
        ))}
      </div>

      <button
        onClick={handlePay}
        disabled={loading}
        style={{
          background: '#2563eb',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: '10px 28px',
          fontSize: 16,
          fontWeight: 600,
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.7 : 1,
        }}
      >
        {loading ? 'Redirecting…' : 'Pay now'}
      </button>

      {error && (
        <p style={{ color: '#dc2626', marginTop: 12 }}>{error}</p>
      )}
    </div>
  )
}
