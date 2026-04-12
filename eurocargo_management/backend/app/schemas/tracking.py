from typing import Optional
from pydantic import BaseModel


class TrackingEvent(BaseModel):
    date: str          # as returned by track24 — e.g. "2026-04-07 14:32"
    location: str
    description: str


class TrackingResponse(BaseModel):
    tracking_code: str
    carrier: Optional[str] = None
    events: list[TrackingEvent] = []
