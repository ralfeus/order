'''Revolut Merchant API client (scaffolded — requires REVOLUT_API_KEY in config)'''
import hashlib
import hmac
import logging
from decimal import Decimal

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class RevolutClient:
    def __init__(self):
        self.base_url = settings.revolut_api_url
        self.api_key = settings.revolut_api_key

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def create_order(
        self,
        amount_eur: Decimal,
        shipment_id: int,
        description: str,
        return_url: str,
    ) -> dict:
        '''Create a Revolut payment order and return the raw API response.

        Returns dict with at minimum:
          id         — Revolut order ID
          checkout_url — URL to redirect the customer to for payment
        '''
        payload = {
            'amount': int(amount_eur * 100),  # Revolut expects minor units (cents)
            'currency': 'EUR',
            'description': description,
            'metadata': {'shipment_id': str(shipment_id)},
            'redirect_url': return_url,
        }
        with httpx.Client() as client:
            response = client.post(
                f'{self.base_url}/orders',
                json=payload,
                headers=self._headers(),
            )
        response.raise_for_status()
        return response.json()

    def get_order(self, revolut_order_id: str) -> dict:
        '''Retrieve a Revolut order by ID.'''
        with httpx.Client() as client:
            response = client.get(
                f'{self.base_url}/orders/{revolut_order_id}',
                headers=self._headers(),
            )
        response.raise_for_status()
        return response.json()

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        '''Verify the Revolut webhook HMAC-SHA256 signature.'''
        if not settings.revolut_webhook_secret:
            logger.warning('REVOLUT_WEBHOOK_SECRET not configured — skipping verification')
            return True
        expected = hmac.new(
            settings.revolut_webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


revolut_client = RevolutClient()
