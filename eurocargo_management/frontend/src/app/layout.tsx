import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Eurocargo Management',
  description: 'Shipment management and payment portal',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
