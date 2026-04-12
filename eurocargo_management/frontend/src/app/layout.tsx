import type { Metadata } from 'next'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Eurocargo Management',
  description: 'Shipment management and payment portal',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Collect all ECM_* vars at request time — no manual updates needed for new vars
  const runtimeEnv = Object.fromEntries(
    Object.entries(process.env).filter(([k]) => k.startsWith('ECM_'))
  )
  console.log('Runtime environment variables:', runtimeEnv);

  return (
    <html lang="en">
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__ENV__ = ${JSON.stringify(runtimeEnv)}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  )
}
