interface TrackingEvent {
  date: string
  location: string
  description: string
}

interface TrackingData {
  tracking_code: string
  carrier: string | null
  events: TrackingEvent[]
}

interface Props {
  tracking: TrackingData | null
  error?: string
}

export default function TrackingTimeline({ tracking, error }: Props) {
  if (error) {
    return (
      <section style={sectionStyle}>
        <h2 style={headingStyle}>Tracking</h2>
        <p style={{ color: '#6b7280', fontSize: 14 }}>{error}</p>
      </section>
    )
  }

  if (!tracking) return null

  const { carrier, events } = tracking

  return (
    <section style={sectionStyle}>
      <h2 style={headingStyle}>
        Tracking
        {carrier && <span style={{ fontWeight: 400, fontSize: 14, color: '#6b7280', marginLeft: 8 }}>via {carrier}</span>}
      </h2>

      {events.length === 0 ? (
        <p style={{ color: '#6b7280', fontSize: 14 }}>No tracking events yet. Check back soon.</p>
      ) : (
        <ol style={{ listStyle: 'none', margin: 0, padding: 0 }}>
          {events.map((ev, i) => (
            <li key={i} style={{ display: 'flex', gap: 16, paddingBottom: 20, position: 'relative' }}>
              {/* Vertical line */}
              {i < events.length - 1 && (
                <div style={{
                  position: 'absolute',
                  left: 7,
                  top: 18,
                  bottom: 0,
                  width: 2,
                  background: '#e5e7eb',
                }} />
              )}
              {/* Dot */}
              <div style={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                background: i === 0 ? '#1d4ed8' : '#d1d5db',
                border: '2px solid #fff',
                boxShadow: '0 0 0 2px ' + (i === 0 ? '#1d4ed8' : '#d1d5db'),
                flexShrink: 0,
                marginTop: 2,
                zIndex: 1,
              }} />
              {/* Content */}
              <div>
                <p style={{ margin: 0, fontWeight: 600, fontSize: 14 }}>{ev.description}</p>
                {ev.location && (
                  <p style={{ margin: '2px 0 0', fontSize: 13, color: '#6b7280' }}>{ev.location}</p>
                )}
                <p style={{ margin: '2px 0 0', fontSize: 12, color: '#9ca3af' }}>{ev.date}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

const sectionStyle: React.CSSProperties = {
  background: '#f9f9f9',
  borderRadius: 8,
  padding: 24,
  marginBottom: 24,
}

const headingStyle: React.CSSProperties = {
  fontSize: 18,
  marginTop: 0,
  marginBottom: 16,
}
