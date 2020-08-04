from functools import reduce

from app.models import ShippingRate

box_weights = {
    30000: 2200,
    20000: 1900,
    15000: 1400,
    10000: 1000,
    5000: 500,
    2000: 250
}

def get_box_weight(package_weight):
    return reduce(
        lambda acc, box: box[1] if package_weight < box[0] else acc,
        box_weights.items()
    ) if package_weight > 0 \
    else 0

def get_shipment_cost(destination, weight):
    '''
    Returns shipping cost to provided destination for provided weight

    :param destination: destination (mostly country)
    :param weight: shipment weight in grams
    '''
    for rate in ShippingRate.query \
                .filter_by(destination=destination) \
                .order_by(ShippingRate.weight):
        if weight < rate.weight:
            return rate.rate
    raise Exception("No rates found")
