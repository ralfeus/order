from sqlalchemy import Column, Integer, Numeric, String

from app.core.database import Base


class ShippingFlatRate(Base):
    """KR → EU flat rate per kg, shared across all carriers."""
    __tablename__ = 'shipping_flat_rates'

    id = Column(Integer, primary_key=True)
    rate_per_kg = Column(Numeric(10, 2), nullable=False)


class ShippingRateEntry(Base):
    """Per-carrier, per-destination rate table entry.

    The applicable entry for a shipment is the one with the smallest
    max_weight_kg that is still >= the shipment weight.
    """
    __tablename__ = 'shipping_rate_entries'

    id = Column(Integer, primary_key=True)
    shipment_type_code = Column(String(16), nullable=False)
    country = Column(String(2), nullable=False)
    max_weight_kg = Column(Numeric(10, 3), nullable=False)
    cost = Column(Numeric(10, 2), nullable=False)
