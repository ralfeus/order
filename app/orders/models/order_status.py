
import enum


class OrderStatus(enum.Enum):
    ''' Sale orders statuses '''
    draft = 0
    pending = 1
    can_be_paid = 2
    po_created = 3
    packed = 4
    shipped = 5
    cancelled = 6
    ready_to_ship = 7
    at_warehouse = 8
