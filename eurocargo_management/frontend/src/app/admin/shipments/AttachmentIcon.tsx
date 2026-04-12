'use client'

import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'

interface Attachment {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  uploaded_at: string
}

interface Props {
  token: string
  attachments: Attachment[]
  apiUrl: string
}

interface PopupPos { top: number; left: number }

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function AttachmentIcon({ token, attachments, apiUrl }: Props) {
  const [pos, setPos] = useState<PopupPos | null>(null)
  const iconRef = useRef<HTMLSpanElement>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Close popup on scroll/resize so it doesn't drift
  useEffect(() => {
    if (!pos) return
    const close = () => setPos(null)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [pos])

  if (attachments.length === 0) return <span style={{ color: '#9ca3af' }}>—</span>

  function handleMouseEnter() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    if (iconRef.current) {
      const rect = iconRef.current.getBoundingClientRect()
      setPos({ top: rect.bottom + 6, left: rect.left })
    }
  }

  function handleMouseLeave() {
    timeoutRef.current = setTimeout(() => setPos(null), 300)
  }

  const popup = pos && createPortal(
    <div
      style={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        zIndex: 9999,
        background: '#fff',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
        minWidth: 280,
        padding: 8,
      }}
      onMouseEnter={() => { if (timeoutRef.current) clearTimeout(timeoutRef.current) }}
      onMouseLeave={handleMouseLeave}
    >
      {attachments.map(a => (
        <a
          key={a.id}
          href={`${apiUrl}/api/v1/shipments/${token}/attachments/${a.id}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 8px',
            borderRadius: 6,
            textDecoration: 'none',
            color: '#1d4ed8',
            fontSize: 13,
          }}
        >
          <span style={{ fontSize: 16 }}>{iconForMime(a.content_type)}</span>
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {a.filename}
          </span>
          <span style={{ color: '#6b7280', whiteSpace: 'nowrap' }}>
            {formatBytes(a.size_bytes)}
          </span>
        </a>
      ))}
    </div>,
    document.body,
  )

  return (
    <>
      <span
        ref={iconRef}
        style={{ cursor: 'pointer', fontSize: 18, userSelect: 'none', display: 'inline-block' }}
        title={`${attachments.length} attachment${attachments.length !== 1 ? 's' : ''}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        📎 {attachments.length}
      </span>
      {popup}
    </>
  )
}

function iconForMime(mime: string): string {
  if (mime === 'application/pdf') return '📄'
  if (mime.startsWith('image/')) return '🖼️'
  return '📎'
}
