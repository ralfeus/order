from decimal import Decimal
from typing import Optional

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
    multiplier = Column(Numeric(10, 4), nullable=False, default=Decimal('1.0'))

    shipments = relationship('Shipment', back_populates='shipment_type')

    @staticmethod
    def volumetric_weight_kg(
        length_cm: Optional[Decimal],
        width_cm: Optional[Decimal],
        height_cm: Optional[Decimal],
    ) -> Decimal:
        """Return volumetric weight in kg: L × W × H (cm) / 5000.

        Returns 0 when any dimension is missing or zero.
        """
        if length_cm and width_cm and height_cm:
            return Decimal(length_cm) * Decimal(width_cm) * Decimal(height_cm) / Decimal(5000)
        return Decimal(0)

    def calculate_cost(
        self,
        weight_kg: Decimal,
        country: str,
        db: Session,
        length_cm: Optional[Decimal] = None,
        width_cm: Optional[Decimal] = None,
        height_cm: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate shipment cost: flat rate (KR→EU) × billable weight + table rate (EU local).

        Billable weight = max(actual weight, volumetric weight).
        Volumetric weight = L × W × H (cm) / 5000 kg.

        Raises ValueError if no matching rate is found.
        """
        from app.models.shipping_rate import ShippingFlatRate, ShippingRateEntry

        weight_kg = Decimal(str(weight_kg))
        vol_kg = self.volumetric_weight_kg(length_cm, width_cm, height_cm)
        billable_kg = max(weight_kg, vol_kg)

        flat = db.query(ShippingFlatRate).first()
        if flat is None:
            raise ValueError('No flat rate configured')

        entry = (
            db.query(ShippingRateEntry)
            .filter(
                ShippingRateEntry.shipment_type_code == self.code,
                ShippingRateEntry.country == country,
                ShippingRateEntry.max_weight_kg >= billable_kg,
            )
            .order_by(ShippingRateEntry.max_weight_kg)
            .first()
        )
        if entry is None:
            raise ValueError(
                f'No rate for carrier {self.code}, country {country}, '
                f'weight {weight_kg} kg (billable {billable_kg} kg)'
            )

        return flat.rate_per_kg * billable_kg + entry.cost * self.multiplier

    def create_consignment(self, shipment, db: Session):
        """Create a consignment with the carrier. Override in each subclass."""
        raise NotImplementedError(f'{self.__class__.__name__} has no consignment integration yet')
