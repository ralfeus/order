## Design Context

### Users
Internal logistics/warehouse ops team using this daily from a desktop browser. Speed, scanability, and information density are the primary values. They work through many shipments quickly — status changes, tracking codes, payment toggles — and every extra click or visual distraction is friction. The customer-facing portal (`/shipments/[token]`) is secondary: customers visit once to check status and pay. Both surfaces share a visual language but the admin view must prioritize density.

### Brand Personality
Dense, reliable, workmanlike. The interface should feel like a well-printed cargo manifest — every element justified, no decoration for its own sake. Operators trust it because it's precise, not because it's beautiful. Think: a fabric care label, a logistics barcode sheet, a well-typeset invoice. Not sterile, but completely unsentimental.

### Aesthetic Direction
- **Theme**: Light. Daylight office and warehouse use.
- **Palette**: Warm-neutral base (slightly amber-tinted stone, not cool gray) with a single sharp accent — deep amber/orange, the colour of a shipping label. Uses OKLCH throughout. No gradient text, no glows.
- **Typography**: Barlow Semi Condensed for headings and column headers (efficient, slightly condensed, manufactured feel); Geist for body/data text (built for dense UIs and data tables). Both available on Google Fonts.
- **Density**: Tight table rows, compact padding, high information per screen. Generous spacing only at the macro level (page margins, section breaks).
- **No decoration**: No cards-on-cards, no shadows as style, no icon badges above headings. Status indicators use background tints, not side-stripe borders.

### Design Principles
1. **Density earns trust.** Operators read tables fast. Don't pad cells to breathe — let the data fill the space.
2. **One accent, used sparingly.** The amber accent signals action and attention. Everything else is neutral.
3. **State is the design.** Shipment status, paid/unpaid, tracking present/absent — these states carry the visual weight. Make them unmissable.
4. **No modal-first thinking.** Inline edits (tracking codes), inline toggles (paid), inline selects (status). Minimize context switches.
5. **Customer portal inherits the same tokens, loosened.** More whitespace, slightly larger type, same palette — but not a different product.
