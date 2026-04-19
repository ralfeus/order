'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { getApiUrl } from '@/lib/env'

interface RateEntry {
  id: number
  country: string
  max_weight_kg: string
  cost: string
}

interface CarrierRates {
  code: string
  name: string
  multiplier: string
  entries: RateEntry[]
}

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : ''
}

/** Build a pivot: rows = countries, cols = weight tiers (sorted asc) */
function pivot(entries: RateEntry[]): {
  weights: string[]
  countries: string[]
  table: Record<string, Record<string, string>>
} {
  const weightsSet = new Set<string>()
  const countriesSet = new Set<string>()
  const table: Record<string, Record<string, string>> = {}

  for (const e of entries) {
    weightsSet.add(e.max_weight_kg)
    countriesSet.add(e.country)
    if (!table[e.country]) table[e.country] = {}
    table[e.country][e.max_weight_kg] = e.cost
  }

  const weights = [...weightsSet].sort((a, b) => Number(a) - Number(b))
  const countries = [...countriesSet].sort()
  return { weights, countries, table }
}

function applyMultiplier(cost: string, multiplier: string): string {
  const result = Number(cost) * Number(multiplier)
  return isNaN(result) ? '—' : result.toFixed(2)
}

export default function AdminRatesPage() {
  const router = useRouter()
  const apiUrl = getApiUrl()

  const [carriers, setCarriers] = useState<CarrierRates[]>([])
  const [selectedCode, setSelectedCode] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [multiplierDraft, setMultiplierDraft] = useState<string>('')
  const [multiplierSaving, setMultiplierSaving] = useState(false)
  const [multiplierError, setMultiplierError] = useState<string | null>(null)
  const saveTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const authHeaders = useCallback((): Record<string, string> => {
    const token = getCookie('admin_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [])

  const fetchRates = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/admin/rates`, { headers: authHeaders() })
      if (res.status === 401 || res.status === 403) { router.push('/admin/login'); return }
      if (!res.ok) throw new Error('Failed to load rates')
      const data: CarrierRates[] = await res.json()
      setCarriers(data)
      if (data.length > 0 && !selectedCode) {
        setSelectedCode(data[0].code)
        setMultiplierDraft(data[0].multiplier)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [apiUrl, authHeaders, router, selectedCode])

  useEffect(() => { fetchRates() }, [fetchRates])

  const carrier = carriers.find(c => c.code === selectedCode) ?? null

  function handleCarrierChange(code: string) {
    setSelectedCode(code)
    const c = carriers.find(x => x.code === code)
    if (c) setMultiplierDraft(c.multiplier)
    setMultiplierError(null)
  }

  function handleMultiplierChange(raw: string) {
    setMultiplierDraft(raw)
    setMultiplierError(null)

    const val = Number(raw)
    if (!raw || isNaN(val) || val <= 0) {
      setMultiplierError('Must be a positive number')
      return
    }

    if (saveTimeout.current) clearTimeout(saveTimeout.current)
    saveTimeout.current = setTimeout(() => saveMultiplier(raw), 600)
  }

  async function saveMultiplier(value: string) {
    if (!selectedCode) return
    setMultiplierSaving(true)
    try {
      const res = await fetch(
        `${apiUrl}/api/v1/admin/rates/${selectedCode}/multiplier`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ multiplier: value }),
        },
      )
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setMultiplierError(data.detail ?? 'Failed to save')
        return
      }
      const updated: CarrierRates = await res.json()
      setCarriers(prev => prev.map(c => c.code === updated.code ? updated : c))
    } catch {
      setMultiplierError('Network error')
    } finally {
      setMultiplierSaving(false)
    }
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

  const { weights, countries, table } = carrier
    ? pivot(carrier.entries)
    : { weights: [], countries: [], table: {} }

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
          Shipping Rates
        </h1>
      </div>

      {/* Controls row */}
      <div style={{
        display: 'flex',
        gap: 'var(--space-8)',
        alignItems: 'flex-start',
        marginBottom: 'var(--space-6)',
        flexWrap: 'wrap',
      }}>
        {/* Carrier selector */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
          <label style={{
            fontFamily: 'var(--font-display)',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'var(--text-2)',
          }}>
            Carrier
          </label>
          <select
            value={selectedCode}
            onChange={e => handleCarrierChange(e.target.value)}
            style={{ minWidth: 200, fontSize: 13 }}
          >
            {carriers.map(c => (
              <option key={c.code} value={c.code}>{c.name} ({c.code})</option>
            ))}
          </select>
        </div>

        {/* Multiplier */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
          <label style={{
            fontFamily: 'var(--font-display)',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'var(--text-2)',
          }}>
            Multiplier
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <input
              type="number"
              min="0.0001"
              step="0.01"
              value={multiplierDraft}
              onChange={e => handleMultiplierChange(e.target.value)}
              style={{
                width: 90,
                fontSize: 13,
                borderColor: multiplierError ? 'var(--danger)' : undefined,
              }}
            />
            {multiplierSaving && (
              <span style={{
                fontSize: 11,
                color: 'var(--text-3)',
                fontFamily: 'var(--font-display)',
                letterSpacing: '0.03em',
              }}>
                Saving…
              </span>
            )}
          </div>
          {multiplierError && (
            <span style={{ fontSize: 11, color: 'var(--danger)' }}>{multiplierError}</span>
          )}
          <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
            Rate shown = table cost × multiplier
          </span>
        </div>
      </div>

      {/* Rate table */}
      {carrier && countries.length === 0 && (
        <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No rate entries for {carrier.name}.</p>
      )}

      {carrier && countries.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--bg-sunken)' }}>
                <th style={{ ...thStyle, textAlign: 'left' }}>Country</th>
                {weights.map(w => (
                  <th key={w} style={{ ...thStyle, textAlign: 'right' }}>
                    ≤ {Number(w).toFixed(3)} kg
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {countries.map((country, i) => (
                <tr
                  key={country}
                  style={{
                    background: i % 2 === 0 ? 'var(--bg)' : 'var(--bg-raised)',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <td style={{ padding: '6px 10px', fontWeight: 500 }}>{country}</td>
                  {weights.map(w => {
                    const raw = table[country]?.[w]
                    return (
                      <td key={w} style={{ padding: '6px 10px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                        {raw != null
                          ? `€${applyMultiplier(raw, multiplierDraft)}`
                          : <span style={{ color: 'var(--text-3)' }}>—</span>
                        }
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

const thStyle: React.CSSProperties = {
  padding: '7px 10px',
  fontFamily: 'var(--font-display)',
  fontWeight: 600,
  fontSize: 11,
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
  color: 'var(--text-2)',
  whiteSpace: 'nowrap',
  borderBottom: '1px solid var(--border)',
}
