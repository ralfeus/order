'use client'

import { useRef, useState } from 'react'

interface Attachment {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  uploaded_at: string
}

interface Props {
  token: string
  apiUrl: string
  initialAttachments: Attachment[]
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function AttachmentManager({ token, apiUrl, initialAttachments }: Props) {
  const [attachments, setAttachments] = useState<Attachment[]>(initialAttachments)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const baseUrl = `${apiUrl}/api/v1/shipments/${token}/attachments`

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    setError(null)
    setUploading(true)

    for (const file of Array.from(files)) {
      const body = new FormData()
      body.append('file', file)
      const res = await fetch(baseUrl, { method: 'POST', body })
      if (res.ok) {
        const created: Attachment = await res.json()
        setAttachments(prev => [...prev, created])
      } else {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        setError(detail.detail ?? 'Upload failed')
      }
    }

    setUploading(false)
    if (inputRef.current) inputRef.current.value = ''
  }

  async function handleDelete(id: number, filename: string) {
    if (!confirm(`Remove "${filename}"?`)) return
    const res = await fetch(`${baseUrl}/${id}`, { method: 'DELETE' })
    if (res.ok) {
      setAttachments(prev => prev.filter(a => a.id !== id))
    } else {
      setError('Failed to delete attachment')
    }
  }

  function downloadUrl(id: number) {
    return `${baseUrl}/${id}`
  }

  return (
    <section style={{ marginTop: 32 }}>
      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Attachments</h2>

      {attachments.length === 0 && (
        <p style={{ color: '#888', fontSize: 14, marginBottom: 12 }}>No files attached yet.</p>
      )}

      {attachments.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, marginBottom: 16 }}>
          {attachments.map(a => (
            <li key={a.id} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '8px 0', borderBottom: '1px solid #eee',
            }}>
              <span style={{ flex: 1, fontSize: 14, wordBreak: 'break-all' }}>
                {a.filename}
              </span>
              <span style={{ color: '#888', fontSize: 12, whiteSpace: 'nowrap' }}>
                {formatBytes(a.size_bytes)}
              </span>
              <a
                href={downloadUrl(a.id)}
                target="_blank"
                rel="noreferrer"
                style={linkStyle('#2563eb')}
              >
                View
              </a>
              <button
                onClick={() => handleDelete(a.id, a.filename)}
                style={linkStyle('#dc2626')}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && (
        <p style={{ color: '#dc2626', fontSize: 13, marginBottom: 8 }}>{error}</p>
      )}

      <label style={{
        display: 'inline-block',
        padding: '8px 16px',
        background: uploading ? '#9ca3af' : '#2563eb',
        color: '#fff',
        borderRadius: 6,
        cursor: uploading ? 'not-allowed' : 'pointer',
        fontSize: 14,
        fontWeight: 500,
      }}>
        {uploading ? 'Uploading…' : '+ Add file'}
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,image/jpeg,image/png"
          onChange={handleUpload}
          disabled={uploading}
          style={{ display: 'none' }}
        />
      </label>
      <p style={{ color: '#888', fontSize: 12, marginTop: 6 }}>
        PDF, JPEG or PNG · max 10 MB each
      </p>
    </section>
  )
}

function linkStyle(color: string): React.CSSProperties {
  return {
    background: 'none',
    border: 'none',
    padding: 0,
    color,
    cursor: 'pointer',
    fontSize: 13,
    textDecoration: 'underline',
    whiteSpace: 'nowrap',
  }
}
