import { notFound } from 'next/navigation'
import PayButton from './PayButton'
import AttachmentManager from './AttachmentManager'

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
  shipment_type: ShipmentType
  tracking_code: string | null
  amount_eur: string | null
  status: string
  shipment_url: string
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

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
      <span style={{ color: '#666', minWidth: 120 }}>{label}</span>
      <span style={{ fontWeight: 500, textAlign: 'right' }}>{value}</span>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colour = status === 'paid' ? '#16a34a' : '#d97706'
  return (
    <span style={{
      background: colour,
      color: '#fff',
      borderRadius: 12,
      padding: '2px 12px',
      fontSize: 13,
      fontWeight: 600,
      textTransform: 'capitalize',
    }}>
      {status}
    </span>
  )
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


  const isPaid = shipment.status !== 'pending'

  return (
    <main style={{ maxWidth: 600, margin: '40px auto', fontFamily: 'sans-serif', padding: '0 16px' }}>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Shipment Details</h1>

      <section style={{ background: '#f9f9f9', borderRadius: 8, padding: 24, marginBottom: 24 }}>
        <Row label="Order ID" value={shipment.order_id} />
        <Row label="Carrier" value={`${shipment.shipment_type.name} (${shipment.shipment_type.code})`} />
        <Row label="Recipient" value={shipment.customer_name} />
        <Row label="Address" value={`${shipment.address}, ${shipment.city}, ${shipment.country} ${shipment.zip}`} />
        {shipment.phone && <Row label="Phone" value={shipment.phone} />}
        {shipment.tracking_code && <Row label="Tracking" value={shipment.tracking_code} />}
        <Row label="Amount" value={shipment.amount_eur != null ? `€${Number(shipment.amount_eur).toFixed(2)}` : 'Pending'} />
        <Row label="Status" value={<StatusBadge status={shipment.status} />} />
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

      {!isPaid && shipment.amount_eur != null && (
        <PayButton token={token} amountEur={shipment.amount_eur} />
      )}

      <AttachmentManager
        token={token}
        apiUrl={apiUrl}
        initialAttachments={initialAttachments}
      />
    </main>
  )
}
