from app.models.carrier import BaseCarrier


class GLSCarrier(BaseCarrier):
    __mapper_args__ = {'polymorphic_identity': 'GLS'}

    def create_consignment(self, shipment, db):
        """Create a GLS consignment. TODO: implement GLS API integration."""
        raise NotImplementedError('GLS consignment creation is not yet implemented')
