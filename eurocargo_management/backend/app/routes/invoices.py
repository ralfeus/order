"""Invoice generation endpoint."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from fpdf import FPDF
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.config import Config
from app.models.invoice import Invoice
from app.models.shipment import Shipment
from app.schemas.invoice import PaymentInstructions

logger = logging.getLogger(__name__)
router = APIRouter(tags=['invoices'])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(db: Session, name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a single config value by name."""
    row = db.query(Config).filter_by(name=name).first()
    if row is None or row.value is None:
        return default
    return row.value


def _require_cfg(db: Session, *names: str) -> dict[str, str]:
    """Read multiple config values; raise 503 if any are missing."""
    result: dict[str, str] = {}
    missing = []
    for name in names:
        val = _cfg(db, name)
        if not val:
            missing.append(name)
        else:
            result[name] = val
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f'Missing configuration: {", ".join(missing)}. Set these in the config table.',
        )
    return result


def _next_invoice_number(db: Session, prefix: str) -> str:
    """Generate the next sequential invoice number for the current year."""
    year = datetime.now(timezone.utc).year
    like = f'{prefix}-{year}-%'
    count = db.query(Invoice).filter(Invoice.invoice_number.like(like)).count()
    return f'{prefix}-{year}-{count + 1:04d}'


def _build_pdf(
    invoice_number: str,
    shipment: Shipment,
    cfg: dict[str, str],
) -> bytes:
    """Render a simple A4 invoice PDF and return raw bytes."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ---- Header: recipient (seller) ----
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, cfg['recipient_name'], ln=True)
    pdf.set_font('Helvetica', '', 10)
    for line in cfg['recipient_address'].split(','):
        pdf.cell(0, 6, line.strip(), ln=True)
    if cfg.get('recipient_vat'):
        pdf.cell(0, 6, f'VAT: {cfg["recipient_vat"]}', ln=True)
    pdf.ln(6)

    # ---- Invoice metadata ----
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'INVOICE', ln=True)
    pdf.set_font('Helvetica', '', 10)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    pdf.cell(0, 6, f'Invoice number: {invoice_number}', ln=True)
    pdf.cell(0, 6, f'Date: {today}', ln=True)
    pdf.ln(6)

    # ---- Bill to (payer) ----
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, 'Bill To:', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, shipment.customer_name, ln=True)
    pdf.cell(0, 6, shipment.address, ln=True)
    pdf.cell(0, 6, f'{shipment.zip} {shipment.city}, {shipment.country}', ln=True)
    pdf.cell(0, 6, shipment.email, ln=True)
    pdf.ln(8)

    # ---- Line items table ----
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(100, 8, 'Description', border=1, fill=True)
    pdf.cell(40, 8, 'Order ref.', border=1, fill=True)
    pdf.cell(0, 8, 'Amount', border=1, fill=True, ln=True)

    pdf.set_font('Helvetica', '', 10)
    description = f'Shipping service ({shipment.shipment_type.code})'
    amount_str = f'EUR {float(shipment.amount_eur):.2f}'
    pdf.cell(100, 8, description, border=1)
    pdf.cell(40, 8, shipment.order_id, border=1)
    pdf.cell(0, 8, amount_str, border=1, ln=True)
    pdf.ln(2)

    # ---- Total ----
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(140, 8, 'Total due:', align='R')
    pdf.cell(0, 8, amount_str, ln=True)
    pdf.ln(10)

    # ---- SEPA payment instructions ----
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, 'Payment Instructions (SEPA Credit Transfer)', ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f'Beneficiary: {cfg["recipient_name"]}', ln=True)
    pdf.cell(0, 6, f'IBAN: {cfg["recipient_iban"]}', ln=True)
    pdf.cell(0, 6, f'BIC: {cfg["recipient_bic"]}', ln=True)
    if cfg.get('recipient_bank_name'):
        pdf.cell(0, 6, f'Bank: {cfg["recipient_bank_name"]}', ln=True)
    pdf.cell(0, 6, f'Amount: EUR {float(shipment.amount_eur):.2f}', ln=True)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, f'Reference: {invoice_number}', ln=True)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.cell(0, 6, 'Please include the reference exactly as shown above.', ln=True)

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post('/shipments/{token}/invoice', response_model=PaymentInstructions, status_code=201)
def generate_invoice(token: str, db: Session = Depends(get_db)):
    """Generate (or return existing) invoice for a shipment."""
    shipment = db.query(Shipment).filter_by(token=token).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')
    if shipment.amount_eur is None:
        raise HTTPException(status_code=422, detail='Shipping cost not yet calculated')

    # Idempotent: return existing invoice if already generated
    existing = db.query(Invoice).filter_by(shipment_id=shipment.id).first()
    if existing:
        return _instructions(existing, shipment, db)

    cfg = _require_cfg(db, 'recipient_name', 'recipient_iban', 'recipient_bic',
                       'recipient_address')
    cfg['recipient_vat'] = _cfg(db, 'recipient_vat') or ''
    cfg['recipient_bank_name'] = _cfg(db, 'recipient_bank_name') or ''
    prefix = _cfg(db, 'invoice_prefix', 'INV')

    invoice_number = _next_invoice_number(db, prefix)
    pdf_bytes = _build_pdf(invoice_number, shipment, cfg)

    invoice = Invoice(
        invoice_number=invoice_number,
        shipment_id=shipment.id,
        pdf_data=pdf_bytes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    logger.info('Invoice %s generated for shipment %s', invoice_number, shipment.id)

    return _instructions(invoice, shipment, db)


@router.get('/shipments/{token}/invoice/pdf')
def get_invoice_pdf(token: str, db: Session = Depends(get_db)):
    """Serve the invoice PDF inline."""
    shipment = db.query(Shipment).filter_by(token=token).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')

    invoice = db.query(Invoice).filter_by(shipment_id=shipment.id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail='Invoice not yet generated')

    return Response(
        content=invoice.pdf_data,
        media_type='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{invoice.invoice_number}.pdf"'},
    )


def _instructions(invoice: Invoice, shipment: Shipment, db: Session) -> PaymentInstructions:
    cfg = _require_cfg(db, 'recipient_name', 'recipient_iban', 'recipient_bic')
    bank_name = _cfg(db, 'recipient_bank_name') or ''
    return PaymentInstructions(
        invoice_number=invoice.invoice_number,
        amount_eur=f'{float(shipment.amount_eur):.2f}',
        recipient_name=cfg['recipient_name'],
        iban=cfg['recipient_iban'],
        bic=cfg['recipient_bic'],
        bank_name=bank_name,
        reference=invoice.invoice_number,
        created_at=invoice.created_at,
    )
