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

  // Multiplier editing state
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

    // Debounce save by 600 ms
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

  if (loading) return <main style={mainStyle}><p>Loading…</p></main>
  if (error)   return <main style={mainStyle}><p style={{ color: '#dc2626' }}>{error}</p></main>

  const { weights, countries, table } = carrier ? pivot(carrier.entries) : { weights: [], countries: [], table: {} }
  const effectiveMultiplier = multiplierDraft

  return (
    <main style={mainStyle}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', marginBottom: 24, flexWrap: 'wrap' }}>
        {/* Carrier selector */}
        <label style={labelStyle}>
          Carrier
          <select
            value={selectedCode}
            onChange={e => handleCarrierChange(e.target.value)}
            style={selectStyle}
          >
            {carriers.map(c => (
              <option key={c.code} value={c.code}>{c.name} ({c.code})</option>
            ))}
          </select>
        </label>

        {/* Multiplier */}
        <label style={labelStyle}>
          Multiplier
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="number"
              min="0.0001"
              step="0.01"
              value={multiplierDraft}
              onChange={e => handleMultiplierChange(e.target.value)}
              style={{
                ...inputStyle,
                borderColor: multiplierError ? '#dc2626' : '#d1d5db',
              }}
            />
            {multiplierSaving && <span style={{ fontSize: 12, color: '#6b7280' }}>Saving…</span>}
          </div>
          {multiplierError && (
            <span style={{ fontSize: 12, color: '#dc2626' }}>{multiplierError}</span>
          )}
          <span style={{ fontSize: 11, color: '#9ca3af' }}>
            Displayed rates = table cost × multiplier
          </span>
        </label>
      </div>

      {/* Rate table */}
      {carrier && countries.length === 0 && (
        <p style={{ color: '#6b7280' }}>No rate entries for {carrier.name}.</p>
      )}

      {carrier && countries.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                <Th style={{ textAlign: 'left' }}>Country</Th>
                {weights.map(w => (
                  <Th key={w}>≤ {Number(w).toFixed(3)} kg</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {countries.map((country, i) => (
                <tr
                  key={country}
                  style={{ background: i % 2 === 0 ? '#fff' : '#f9fafb', borderBottom: '1px solid #e5e7eb' }}
                >
                  <td style={{ padding: '8px 12px', fontWeight: 600 }}>{country}</td>
                  {weights.map(w => {
                    const raw = table[country]?.[w]
                    return (
                      <td key={w} style={{ padding: '8px 12px', textAlign: 'right' }}>
                        {raw != null
                          ? `€${applyMultiplier(raw, effectiveMultiplier)}`
                          : <span style={{ color: '#d1d5db' }}>—</span>
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
    </main>
  )
}

function Th({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th style={{
      padding: '10px 12px',
      fontWeight: 600,
      color: '#374151',
      whiteSpace: 'nowrap',
      textAlign: 'right',
      ...style,
    }}>
      {children}
    </th>
  )
}

const mainStyle: React.CSSProperties = {
  maxWidth: 1100,
  margin: '32px auto',
  fontFamily: 'sans-serif',
  padding: '0 16px',
}

const labelStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  fontSize: 13,
  fontWeight: 600,
  color: '#374151',
}

const selectStyle: React.CSSProperties = {
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '7px 10px',
  fontSize: 14,
  minWidth: 200,
}

const inputStyle: React.CSSProperties = {
  border: '1px solid #d1d5db',
  borderRadius: 6,
  padding: '7px 10px',
  fontSize: 14,
  width: 100,
  outline: 'none',
}
