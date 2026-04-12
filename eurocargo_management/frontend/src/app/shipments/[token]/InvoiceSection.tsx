'use client'

import { useState } from 'react'

interface PaymentInstructions {
  invoice_number: string
  amount_eur: string
  recipient_name: string
  iban: string
  bic: string
  bank_name: string
  reference: string
}

interface Props {
  token: string
  amountEur: string
  apiUrl: string
}

export default function InvoiceSection({ token, amountEur, apiUrl }: Props) {
  const [instructions, setInstructions] = useState<PaymentInstructions | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handlePay() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${apiUrl}/api/v1/shipments/${token}/invoice`, {
        method: 'POST',
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail ?? 'Failed to generate invoice')
        return
      }
      const data: PaymentInstructions = await res.json()
      setInstructions(data)
      // Open PDF in a new tab
      window.open(`${apiUrl}/api/v1/shipments/${token}/invoice/pdf`, '_blank')
    } catch {
      setError('Network error — please try again')
    } finally {
      setLoading(false)
    }
  }

  if (instructions) {
    return (
      <section style={sectionStyle}>
        <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16 }}>Payment Instructions</h2>
        <p style={{ marginTop: 0, color: '#374151', fontSize: 14 }}>
          Please make a SEPA bank transfer using the details below.
          Use the invoice number as the payment reference.
        </p>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <tbody>
            <IRow label="Beneficiary"     value={instructions.recipient_name} />
            <IRow label="IBAN"            value={<code style={codeStyle}>{instructions.iban}</code>} />
            <IRow label="BIC / SWIFT"     value={<code style={codeStyle}>{instructions.bic}</code>} />
            {instructions.bank_name && <IRow label="Bank" value={instructions.bank_name} />}
            <IRow label="Amount"          value={<strong>€{instructions.amount_eur}</strong>} />
            <IRow
              label="Reference"
              value={
                <strong style={{ color: '#1d4ed8' }}>
                  {instructions.reference}
                </strong>
              }
            />
          </tbody>
        </table>

        <p style={{ marginBottom: 0, fontSize: 13, color: '#6b7280' }}>
          ⚠️ Include the reference <strong>{instructions.reference}</strong> exactly as shown so we can match your payment.
        </p>

        <button
          onClick={() => window.open(`${apiUrl}/api/v1/shipments/${token}/invoice/pdf`, '_blank')}
          style={secondaryBtn}
        >
          📄 Open invoice again
        </button>
      </section>
    )
  }

  return (
    <div style={{ marginBottom: 16 }}>
      {error && <p style={{ color: '#dc2626', fontSize: 14, marginBottom: 8 }}>{error}</p>}
      <button onClick={handlePay} disabled={loading} style={payBtn}>
        {loading ? 'Generating invoice…' : `Pay €${Number(amountEur).toFixed(2)}`}
      </button>
    </div>
  )
}

function IRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <tr>
      <td style={{ padding: '6px 0', color: '#6b7280', width: 120, verticalAlign: 'top' }}>{label}</td>
      <td style={{ padding: '6px 0', fontWeight: 500 }}>{value}</td>
    </tr>
  )
}

const sectionStyle: React.CSSProperties = {
  background: '#eff6ff',
  border: '1px solid #bfdbfe',
  borderRadius: 8,
  padding: 20,
  marginBottom: 24,
}

const payBtn: React.CSSProperties = {
  background: '#1d4ed8',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  padding: '12px 28px',
  fontSize: 16,
  fontWeight: 600,
  cursor: 'pointer',
}

const secondaryBtn: React.CSSProperties = {
  marginTop: 16,
  background: 'none',
  border: '1px solid #93c5fd',
  borderRadius: 6,
  padding: '6px 14px',
  fontSize: 13,
  cursor: 'pointer',
  color: '#1d4ed8',
}

const codeStyle: React.CSSProperties = {
  fontFamily: 'monospace',
  background: '#dbeafe',
  padding: '1px 6px',
  borderRadius: 4,
}
