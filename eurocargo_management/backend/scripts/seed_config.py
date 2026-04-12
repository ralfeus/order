#!/usr/bin/env python3
"""
Config seeding script — edit the VALUES dict below, then run:

    python scripts/seed_config.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.config import Config  # noqa: F401

# ---------------------------------------------------------------------------
# Edit these values before running in production
# ---------------------------------------------------------------------------
VALUES = {
    # Invoice / SEPA payment
    'invoice_prefix':      'INV',
    'recipient_name':      'EuroCargo GmbH',
    'recipient_address':   'Hauptstraße 1, 10115 Berlin, Germany',
    'recipient_vat':       'DE123456789',
    'recipient_iban':      'DE89370400440532013000',
    'recipient_bic':       'COBADEFFXXX',
    'recipient_bank_name': 'Commerzbank',

    # DHL Parcel DE — Shipping API v2
    # Set dhl_sandbox to 'false' in production
    'dhl_sandbox':           'true',
    'dhl_app_id':            'YOUR_DHL_APP_ID',
    'dhl_app_token':         'YOUR_DHL_APP_TOKEN',
    'dhl_billing_number':    '33333333330101',   # 14-digit account/billing number
    'dhl_product_code':      'V01PAK',           # e.g. V01PAK, V53WPAK, V62WP

    # Shipper address (your warehouse / dispatch address)
    'shipper_name':          'EuroCargo GmbH',
    'shipper_street':        'Hauptstraße 1',
    'shipper_postal_code':   '10115',
    'shipper_city':          'Berlin',
    'shipper_country':       'DE',
    'shipper_email':         'dispatch@eurocargo.example.com',
    'shipper_phone':         '+4930123456789',
}
# ---------------------------------------------------------------------------

def main():
    db = SessionLocal()
    try:
        for name, value in VALUES.items():
            row = db.query(Config).filter_by(name=name).first()
            if row is None:
                db.add(Config(name=name, value=value))
                print(f'  + {name} = {value!r}')
            elif row.value != value:
                row.value = value
                print(f'  ~ {name} = {value!r}')
            else:
                print(f'  = {name} (unchanged)')
        db.commit()
        print('\nDone.')
    except Exception as exc:
        db.rollback()
        print(f'Error: {exc}')
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
