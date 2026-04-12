from datetime import datetime

from pydantic import BaseModel


class InvoiceResponse(BaseModel):
    invoice_number: str
    created_at: datetime

    model_config = {'from_attributes': True}


class PaymentInstructions(BaseModel):
    """SEPA payment details returned alongside the invoice."""
    invoice_number: str
    amount_eur: str
    recipient_name: str
    iban: str
    bic: str
    bank_name: str
    reference: str          # same as invoice_number — shown to user as "use this in reference field"
    created_at: datetime
