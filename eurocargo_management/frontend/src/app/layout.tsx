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
  // console.log('Runtime environment variables:', runtimeEnv);

  return (
    <html lang="en">
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__ENV__ = ${JSON.stringify(runtimeEnv)}`,
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@400;500;600;700&family=Geist:wght@300;400;500;600&display=swap"
          rel="stylesheet"
        />
        <style dangerouslySetInnerHTML={{ __html: `
          *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

          :root {
            /* Surfaces */
            --bg:           oklch(0.98 0.005 75);
            --bg-raised:    oklch(0.96 0.007 75);
            --bg-sunken:    oklch(0.94 0.009 75);
            --bg-overlay:   oklch(1.00 0.000 75);

            /* Borders */
            --border:       oklch(0.88 0.008 75);
            --border-focus: oklch(0.65 0.15 55);

            /* Text */
            --text:         oklch(0.18 0.010 75);
            --text-2:       oklch(0.42 0.012 75);
            --text-3:       oklch(0.62 0.010 75);
            --text-inv:     oklch(0.97 0.003 75);

            /* Accent — amber, used sparingly */
            --accent:       oklch(0.65 0.150 55);
            --accent-hover: oklch(0.57 0.165 55);
            --accent-dim:   oklch(0.94 0.045 75);

            /* Status colours */
            --status-incoming-bg:        oklch(0.94 0.050 75);
            --status-incoming-text:      oklch(0.50 0.130 55);
            --status-warehouse-bg:       oklch(0.93 0.040 240);
            --status-warehouse-text:     oklch(0.40 0.130 240);
            --status-customs-bg:         oklch(0.93 0.035 290);
            --status-customs-text:       oklch(0.42 0.120 290);
            --status-shipped-bg:         oklch(0.92 0.055 155);
            --status-shipped-text:       oklch(0.38 0.130 155);

            /* Paid / unpaid */
            --paid-bg:      oklch(0.92 0.055 155);
            --paid-text:    oklch(0.38 0.130 155);
            --unpaid-bg:    oklch(0.94 0.009 75);
            --unpaid-text:  oklch(0.55 0.010 75);

            /* Danger */
            --danger:       oklch(0.54 0.180 25);
            --danger-bg:    oklch(0.95 0.040 25);

            /* Typography */
            --font-ui:      'Geist', system-ui, sans-serif;
            --font-display: 'Barlow Semi Condensed', system-ui, sans-serif;

            /* Spacing (4pt scale) */
            --space-1:  4px;
            --space-2:  8px;
            --space-3:  12px;
            --space-4:  16px;
            --space-6:  24px;
            --space-8:  32px;
            --space-12: 48px;
            --space-16: 64px;
          }

          html, body {
            background: var(--bg);
            color: var(--text);
            font-family: var(--font-ui);
            font-size: 14px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
          }

          a { color: inherit; }

          button, input, select, textarea {
            font-family: inherit;
            font-size: inherit;
          }

          input, select, textarea {
            background: var(--bg-overlay);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
            outline: none;
            padding: var(--space-2) var(--space-3);
            transition: border-color 0.12s;
          }

          input:focus, select:focus, textarea:focus {
            border-color: var(--border-focus);
          }

          table {
            border-collapse: collapse;
            width: 100%;
          }
        `}} />
      </head>
      <body>{children}</body>
    </html>
  )
}
