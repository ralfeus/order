from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .routes import shipment_types, shipments, revolut

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
app.include_router(revolut.router, prefix='/api/v1')


@app.get('/health')
def health():
    return {'status': 'ok'}
