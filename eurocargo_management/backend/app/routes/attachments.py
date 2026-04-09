"""Shipment attachment CRUD endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.shipment import Shipment
from app.models.shipment_attachment import (
    ShipmentAttachment,
    ALLOWED_MIME_TYPES,
    MAX_SIZE_BYTES,
)
from app.schemas.attachment import AttachmentMeta

logger = logging.getLogger(__name__)
router = APIRouter(tags=['attachments'])


def _get_shipment(token: str, db: Session) -> Shipment:
    shipment = db.query(Shipment).filter_by(token=token).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')
    return shipment


def _get_attachment(shipment: Shipment, attachment_id: int) -> ShipmentAttachment:
    attachment = next((a for a in shipment.attachments if a.id == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail='Attachment not found')
    return attachment


@router.post('/shipments/{token}/attachments',
             response_model=AttachmentMeta, status_code=201)
async def upload_attachment(
    token: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a file and attach it to the shipment."""
    shipment = _get_shipment(token, db)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f'Unsupported file type {file.content_type!r}. '
                   f'Allowed: {", ".join(sorted(ALLOWED_MIME_TYPES))}',
        )

    data = await file.read()
    if len(data) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f'File too large ({len(data):,} bytes). Maximum is {MAX_SIZE_BYTES:,} bytes.',
        )

    attachment = ShipmentAttachment(
        shipment_id=shipment.id,
        filename=file.filename or 'attachment',
        content_type=file.content_type,
        size_bytes=len(data),
        data=data,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    logger.info('Attachment %s uploaded for shipment %s (%d bytes)',
                attachment.id, token, len(data))
    return attachment


@router.get('/shipments/{token}/attachments',
            response_model=list[AttachmentMeta])
def list_attachments(token: str, db: Session = Depends(get_db)):
    """List all attachment metadata for a shipment (no binary data)."""
    shipment = _get_shipment(token, db)
    return shipment.attachments


@router.get('/shipments/{token}/attachments/{attachment_id}')
def download_attachment(
    token: str,
    attachment_id: int,
    db: Session = Depends(get_db),
):
    """Download a single attachment."""
    shipment = _get_shipment(token, db)
    attachment = _get_attachment(shipment, attachment_id)
    return Response(
        content=attachment.data,
        media_type=attachment.content_type,
        headers={
            'Content-Disposition': f'inline; filename="{attachment.filename}"',
            'Content-Length': str(attachment.size_bytes),
        },
    )


@router.delete('/shipments/{token}/attachments/{attachment_id}',
               status_code=204)
def delete_attachment(
    token: str,
    attachment_id: int,
    db: Session = Depends(get_db),
):
    """Delete an attachment."""
    shipment = _get_shipment(token, db)
    attachment = _get_attachment(shipment, attachment_id)
    db.delete(attachment)
    db.commit()
    logger.info('Attachment %s deleted from shipment %s', attachment_id, token)
