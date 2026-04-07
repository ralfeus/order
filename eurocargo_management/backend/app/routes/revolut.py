'''Revolut payment creation and webhook handler'''
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.revolut import revolut_client
from app.models.payment import Payment
from app.models.shipment import Shipment
from app.schemas.payment import PaymentCreate, PaymentResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=['payments'])


@router.post('/shipments/{token}/payments', response_model=PaymentResponse, status_code=201)
def create_payment(
    token: str,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
):
    if payload.method not in ('card', 'sepa'):
        raise HTTPException(status_code=422, detail='method must be "card" or "sepa"')

    shipment = db.query(Shipment).filter_by(token=token).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found')
    if shipment.status == 'paid':
        raise HTTPException(status_code=409, detail='Shipment is already paid')

    return_url = f'{settings.base_url}/shipments/{token}'
    description = f'Shipping for order {shipment.order_id}'

    try:
        revolut_order = revolut_client.create_order(
            amount_eur=shipment.amount_eur,
            shipment_id=shipment.id,
            description=description,
            return_url=return_url,
        )
    except Exception as exc:
        logger.exception('Revolut order creation failed for shipment %s', shipment.id)
        raise HTTPException(status_code=502, detail='Payment provider error') from exc

    payment = Payment(
        shipment_id=shipment.id,
        revolut_order_id=revolut_order.get('id'),
        method=payload.method,
        status='pending',
        amount_eur=shipment.amount_eur,
        checkout_url=revolut_order.get('checkout_url'),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.post('/revolut/webhooks', status_code=200)
async def revolut_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get('revolut-signature', '')

    if not revolut_client.verify_webhook(body, signature):
        raise HTTPException(status_code=401, detail='Invalid webhook signature')

    event = await request.json()
    event_type = event.get('event')

    if event_type == 'ORDER_COMPLETED':
        revolut_order_id = event.get('order_id')
        payment = db.query(Payment).filter_by(revolut_order_id=revolut_order_id).first()
        if payment:
            payment.status = 'paid'
            payment.shipment.status = 'paid'
            db.commit()
            logger.info('Shipment %s marked as paid via webhook', payment.shipment_id)

    return {'received': True}
