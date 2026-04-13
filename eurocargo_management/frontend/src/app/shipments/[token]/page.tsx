import { notFound } from 'next/navigation'
import AttachmentManager from './AttachmentManager'
import CarrierSelector from './CarrierSelector'
import InvoiceSection from './InvoiceSection'

interface ShipmentType {
  id: number
  code: string
  name: string
  enabled: boolean
}

interface Attachment {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  uploaded_at: string
}

interface Shipment {
  id: number
  token: string
  order_id: string
  customer_name: string
  email: string
  address: string
  city: string
  country: string
  zip: string
  phone: string | null
  shipment_type: ShipmentType | null
  tracking_code: string | null
  weight_kg: number
  length_cm: number | null
  width_cm: number | null
  height_cm: number | null
  amount_eur: string | null
  status: string
  paid: boolean
  shipment_url: string
}

const STATUS_LABELS: Record<string, string> = {
  incoming:        'Incoming',
  at_warehouse:    'At warehouse',
  customs_cleared: 'Customs cleared',
  shipped:         'Shipped',
}

const STATUS_COLOURS: Record<string, string> = {
  incoming:        '#d97706',
  at_warehouse:    '#2563eb',
  customs_cleared: '#7c3aed',
  shipped:         '#16a34a',
}

async function getAttachments(token: string, apiUrl: string): Promise<Attachment[]> {
  const res = await fetch(`${apiUrl}/api/v1/shipments/${token}/attachments`, { cache: 'no-store' })
  if (!res.ok) return []
  return res.json()
}

async function getShipment(token: string, username?: string): Promise<Shipment | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  const url = new URL(`${apiUrl}/api/v1/shipments/${token}`)
  if (username) url.searchParams.set('user', username)

  const res = await fetch(url.toString(), { cache: 'no-store' })
  if (res.status === 404) return null
  if (!res.ok) throw new Error('Failed to fetch shipment')
  return res.json()
}

export default async function ShipmentPage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>
  searchParams: Promise<{ user?: string }>
}) {
  const { token } = await params
  const { user } = await searchParams
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  const [shipment, initialAttachments] = await Promise.all([
    getShipment(token, user),
    getAttachments(token, apiUrl),
  ])

  if (!shipment) notFound()

  return (
    <main style={{ maxWidth: 600, margin: '40px auto', fontFamily: 'sans-serif', padding: '0 16px' }}>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Shipment Details</h1>

      <section style={{ background: '#f9f9f9', borderRadius: 8, padding: 24, marginBottom: 24 }}>
        <Row label="Order ID"   value={shipment.order_id} />
        <Row label="Carrier"    value={
          shipment.shipment_type
            ? `${shipment.shipment_type.name} (${shipment.shipment_type.code})`
            : <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>Not selected yet</span>
        } />
        <Row label="Recipient"  value={shipment.customer_name} />
        <Row label="Address"    value={`${shipment.address}, ${shipment.city}, ${shipment.country} ${shipment.zip}`} />
        {shipment.phone && <Row label="Phone" value={shipment.phone} />}
        {shipment.tracking_code && <Row label="Tracking" value={shipment.tracking_code} />}
        <EmptyRow />
        <Row label='Dimensions' value={
          shipment.length_cm && shipment.width_cm && shipment.height_cm
            ? `${shipment.length_cm} x ${shipment.width_cm} x ${shipment.height_cm} cm`
            : 'N/A'
        } />
        <Row label='Weight' value={`${shipment.weight_kg} kg`} />
        <Row label="Amount"  value={shipment.amount_eur != null ? `€${Number(shipment.amount_eur).toFixed(2)}` : 'Pending'} />
        <Row label="Status"  value={<StatusBadge status={shipment.status} />} />
        <Row label="Payment" value={<PaidBadge paid={shipment.paid} />} />
      </section>

      {shipment.tracking_code && (
        <a
          href={`https://track24.net/?code=${encodeURIComponent(shipment.tracking_code)}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'inline-block',
            marginBottom: 16,
            background: '#1d4ed8',
            color: '#fff',
            borderRadius: 8,
            padding: '10px 20px',
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: 15,
          }}
        >
          🔍 Track parcel
        </a>
      )}

      {!shipment.paid && (
        <CarrierSelector
          token={token}
          currentCarrierCode={shipment.shipment_type?.code ?? null}
        />
      )}

      {!shipment.paid && shipment.amount_eur != null && (
        <InvoiceSection token={token} amountEur={shipment.amount_eur} apiUrl={apiUrl} />
      )}

      <AttachmentManager
        token={token}
        apiUrl={apiUrl}
        initialAttachments={initialAttachments}
      />
    </main>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
      <span style={{ color: '#666', minWidth: 120 }}>{label}</span>
      <span style={{ fontWeight: 500, textAlign: 'right' }}>{value}</span>
    </div>
  )
}

function EmptyRow() {
  return <div style={{ height: 16 }} />
}

function StatusBadge({ status }: { status: string }) {
  const colour = STATUS_COLOURS[status] ?? '#6b7280'
  const label  = STATUS_LABELS[status]  ?? status
  return (
    <span style={{
      background: colour,
      color: '#fff',
      borderRadius: 12,
      padding: '2px 12px',
      fontSize: 13,
      fontWeight: 600,
    }}>
      {label}
    </span>
  )
}

function PaidBadge({ paid }: { paid: boolean }) {
  return (
    <span style={{
      background: paid ? '#16a34a' : '#9ca3af',
      color: '#fff',
      borderRadius: 12,
      padding: '2px 12px',
      fontSize: 13,
      fontWeight: 600,
    }}>
      {paid ? 'Paid' : 'Awaiting payment'}
    </span>
  )
}
