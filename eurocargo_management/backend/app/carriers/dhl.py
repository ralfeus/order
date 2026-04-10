"""DHL Parcel DE carrier — encapsulates all DHL-specific logic.

Config keys required:
  dhl_app_id, dhl_app_token, dhl_billing_number,
  dhl_sandbox (optional, default 'true'),
  dhl_product_code (optional, default 'V01PAK'),
  shipper_name, shipper_street, shipper_postal_code,
  shipper_city, shipper_country,
  shipper_email (optional), shipper_phone (optional)
"""
from __future__ import annotations

import base64
import logging
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.models.carrier import BaseCarrier
from app.models.config import Config
from app.models.shipment_attachment import ShipmentAttachment

logger = logging.getLogger(__name__)

_SANDBOX_URL = 'https://api-sandbox.dhl.com/parcel/de/shipping/v2'
_PROD_URL = 'https://api.dhl.com/parcel/de/shipping/v2'

_REQUIRED_CONFIG = [
    'dhl_app_id',
    'dhl_app_token',
    'dhl_billing_number',
    'shipper_name',
    'shipper_street',
    'shipper_postal_code',
    'shipper_city',
    'shipper_country',
]


class DHLCarrier(BaseCarrier):
    __mapper_args__ = {'polymorphic_identity': 'DHL'}

    def create_consignment(self, shipment, db: Session) -> None:
        """Create a DHL Parcel DE consignment.

        On success:
        - Stores the shipping label as a ShipmentAttachment (PDF).
        - Sets shipment.tracking_code to the DHL tracking/shipment number.
        - Sets shipment.status to 'shipped'.
        """
        cfg = self._load_config(db)
        tracking_number, label_bytes = self._call_dhl_api(shipment, cfg)

        if label_bytes:
            attachment = ShipmentAttachment(
                shipment_id=shipment.id,
                filename=f'{tracking_number}.pdf',
                content_type='application/pdf',
                size_bytes=len(label_bytes),
                data=label_bytes,
            )
            db.add(attachment)
            logger.info('Stored DHL label for shipment %s as attachment', shipment.id)

        shipment.tracking_code = tracking_number
        shipment.status = 'shipped'
        logger.info(
            'DHL consignment created: tracking=%s shipment_id=%s',
            tracking_number,
            shipment.id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_config(self, db: Session) -> dict:
        rows = db.query(Config).all()
        cfg = {r.name: r.value for r in rows if r.value is not None}
        missing = [k for k in _REQUIRED_CONFIG if not cfg.get(k)]
        if missing:
            raise ValueError(f'Missing DHL configuration: {", ".join(missing)}')
        return cfg

    def _base_url(self, cfg: dict) -> str:
        sandbox = cfg.get('dhl_sandbox', 'true').strip().lower()
        return _SANDBOX_URL if sandbox == 'true' else _PROD_URL

    def _auth_header(self, cfg: dict) -> str:
        credentials = f'{cfg["dhl_app_id"]}:{cfg["dhl_app_token"]}'
        encoded = base64.b64encode(credentials.encode()).decode()
        return f'Basic {encoded}'

    def _build_payload(self, shipment, cfg: dict) -> dict:
        return {
            'profile': 'STANDARD_GRUPPENPROFIL',
            'shipments': [
                {
                    'product': cfg.get('dhl_product_code', 'V01PAK'),
                    'billingNumber': cfg['dhl_billing_number'],
                    'refNo': shipment.order_id,
                    'shipper': {
                        'name1': cfg['shipper_name'],
                        'addressStreet': cfg['shipper_street'],
                        'postalCode': cfg['shipper_postal_code'],
                        'city': cfg['shipper_city'],
                        'country': cfg['shipper_country'],
                        'email': cfg.get('shipper_email', ''),
                        'phone': cfg.get('shipper_phone', ''),
                    },
                    'consignee': {
                        'name1': shipment.customer_name,
                        'addressStreet': shipment.address,
                        'postalCode': shipment.zip,
                        'city': shipment.city,
                        'country': shipment.country,
                        'email': shipment.email or '',
                        'phone': shipment.phone or '',
                    },
                    'details': {
                        'weight': {
                            'uom': 'kg',
                            'value': float(shipment.weight_kg),
                        }
                    },
                }
            ],
        }

    def _call_dhl_api(self, shipment, cfg: dict) -> Tuple[str, Optional[bytes]]:
        url = self._base_url(cfg) + '/orders'
        headers = {
            'Authorization': self._auth_header(cfg),
            'Content-Type': 'application/json',
        }
        params = {'labelResponseType': 'b64', 'validate': 'false'}
        payload = self._build_payload(shipment, cfg)

        logger.debug('Calling DHL API: POST %s payload=%s', url, payload)

        try:
            response = httpx.post(
                url,
                json=payload,
                headers=headers,
                params=params,
                timeout=30.0,
            )
        except httpx.TimeoutException as exc:
            raise RuntimeError('DHL API timed out') from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f'DHL API connection error: {exc}') from exc

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f'DHL API returned {response.status_code}: {response.text[:500]}'
            )

        data = response.json()
        items = data.get('items', [])
        if not items:
            raise RuntimeError('DHL API returned no shipment items')

        item = items[0]
        tracking_number = item.get('shipmentNo') or item.get('trackingNo')
        if not tracking_number:
            raise RuntimeError('DHL API returned no tracking number')

        label_b64 = item.get('label', {}).get('b64')
        label_bytes = base64.b64decode(label_b64) if label_b64 else None

        return tracking_number, label_bytes
