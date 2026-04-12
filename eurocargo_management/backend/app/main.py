from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .routes import shipment_types, shipments, attachments, tracking, invoices
from .routes.admin import auth as admin_auth, shipments as admin_shipments, rates as admin_rates, consignments as admin_consignments
import app.carriers  # noqa: F401 — registers polymorphic carrier subclasses

app = FastAPI(title='Eurocargo Management', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.base_url],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(shipment_types.router, prefix='/api/v1')
app.include_router(shipments.router, prefix='/api/v1')
app.include_router(attachments.router, prefix='/api/v1')
app.include_router(tracking.router, prefix='/api/v1')
app.include_router(invoices.router, prefix='/api/v1')
app.include_router(admin_auth.router, prefix='/api/v1/admin')
app.include_router(admin_shipments.router, prefix='/api/v1/admin')
app.include_router(admin_rates.router, prefix='/api/v1/admin')
app.include_router(admin_consignments.router, prefix='/api/v1/admin')


@app.get('/health')
def health():
    return {'status': 'ok'}
