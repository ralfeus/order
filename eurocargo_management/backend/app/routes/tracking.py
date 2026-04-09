"""Shipment tracking endpoint — proxies track24.net."""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.shipment import Shipment
from app.schemas.tracking import TrackingEvent, TrackingResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=['tracking'])

_TRACK24_URL = 'https://track24.net/api/en/get_by_number/{code}'
_TIMEOUT = 10.0


def _parse_events(data: dict[str, Any]) -> tuple[list[TrackingEvent], Optional[str]]:
    """Extract events and detected carrier name from a track24 response dict."""
    events: list[TrackingEvent] = []
    carrier: str | None = None

    # track24 returns a list of carrier result objects under various keys;
    # we pick the first non-empty one.
    results: list[dict] = data.get('data', [])
    for result in results:
        carrier = result.get('name') or carrier
        for checkpoint in result.get('checkpoints', []):
            events.append(TrackingEvent(
                date=str(checkpoint.get('date', '')),
                location=str(checkpoint.get('location', '')),
                description=str(checkpoint.get('status', '')),
            ))
        if events:
            break

    return events, carrier


async def _fetch_tracking(tracking_code: str) -> TrackingResponse:
    url = _TRACK24_URL.format(code=tracking_code)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail='Tracking service timed out')
    except httpx.HTTPStatusError as exc:
        logger.warning('track24 returned %s for %s', exc.response.status_code, tracking_code)
        raise HTTPException(status_code=502, detail='Tracking service error')
    except Exception as exc:
        logger.exception('Unexpected error fetching tracking for %s', tracking_code)
        raise HTTPException(status_code=502, detail='Tracking service error') from exc

    events, carrier = _parse_events(data)
    return TrackingResponse(tracking_code=tracking_code, carrier=carrier, events=events)


@router.get('/shipments/{token}/tracking', response_model=TrackingResponse)
async def get_tracking(token: str, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter_by(token=token).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')
    if not shipment.tracking_code:
        raise HTTPException(status_code=404, detail='No tracking code assigned to this shipment')

    return await _fetch_tracking(shipment.tracking_code)
