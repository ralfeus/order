from decimal import Decimal

from sqlalchemy import Boolean, Column, Integer, Numeric, String
from sqlalchemy.orm import Session, relationship

from app.core.database import Base


class BaseCarrier(Base):
    __tablename__ = 'shipment_types'
    __mapper_args__ = {
        'polymorphic_on': 'code',
        'polymorphic_identity': 'base',
    }

    id = Column(Integer, primary_key=True)
    code = Column(String(16), nullable=False, unique=True)
    name = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    shipments = relationship('Shipment', back_populates='shipment_type')

    def calculate_cost(self, weight_kg: Decimal, country: str, db: Session) -> Decimal:
        """Calculate shipment cost: flat rate (KR→EU) × weight + table rate (EU local).

        Raises ValueError if no matching rate is found.
        """
        from app.models.shipping_rate import ShippingFlatRate, ShippingRateEntry

        flat = db.query(ShippingFlatRate).first()
        if flat is None:
            raise ValueError('No flat rate configured')

        entry = (
            db.query(ShippingRateEntry)
            .filter(
                ShippingRateEntry.shipment_type_code == self.code,
                ShippingRateEntry.country == country,
                ShippingRateEntry.max_weight_kg >= weight_kg,
            )
            .order_by(ShippingRateEntry.max_weight_kg)
            .first()
        )
        if entry is None:
            raise ValueError(
                f'No rate for carrier {self.code}, country {country}, weight {weight_kg} kg'
            )

        return flat.rate_per_kg * weight_kg + entry.cost

    def create_consignment(self, shipment, db: Session):
        """Create a consignment with the carrier. Override in each subclass."""
        raise NotImplementedError(f'{self.__class__.__name__} has no consignment integration yet')
