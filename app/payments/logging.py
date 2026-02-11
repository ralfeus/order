import logging
from typing import Any, MutableMapping, Optional

class PaymentLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        extra = kwargs.setdefault('extra', {})  # Simpler than if-check
        extra.setdefault('payment_id', 'no_ID')  # Non-destructive default
        extra.update(self.extra)
        return msg, kwargs
    
    def set_payment_id(self, payment_id:Any):
        self.extra['payment_id'] = payment_id #type:ignore
    
def get_logger(name: Optional[str] = None, payment_handler: Optional[logging.Handler] = None) -> PaymentLoggerAdapter:
    """Factory: returns configured PaymentLogger."""
    logger = logging.getLogger(name or __name__)
    
    if not logger.handlers:  # Configure once
        if payment_handler is None:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s\t%(levelname)s\t%(name)s:%(funcName)s()[%(filename)s:%(lineno)d]: %(message)s [payment_id=%(payment_id)s]"
            ))
        else:
            handler = payment_handler
        
        logger.addHandler(handler)
        logger.propagate = False
    
    return PaymentLoggerAdapter(logger, {})  # No static extra needed

