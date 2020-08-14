from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from sqlalchemy import inspect

from app import db
from app.import_products import atomy
from app.models import Product

cron = BackgroundScheduler()
# Explicitly kick off the background thread
cron.start()

@cron.scheduled_job(trigger="interval", hours=1)
def import_products():
    products = Product.query.all()
    same = new = modified = 0
    for atomy_product in atomy():
        try:
            product = next(p for p in products if p.id.lstrip('0') == atomy_product['id'].lstrip('0'))
            is_dirty = False
            if product.name != atomy_product['name']:
                product.name = atomy_product['name']
                is_dirty = True
            if product.price != int(atomy_product['price']):
                product.price = int(atomy_product['price'])
                is_dirty = True
            if product.points != int(atomy_product['points']):
                product.points = int(atomy_product['points'])
                is_dirty = True
            if product.available != atomy_product['available']:
                product.available = atomy_product['available']
                is_dirty = True
            if is_dirty:
                product.when_changed = datetime.now()
                modified += 1
            else:
                same += 1

            products.remove(product)
        except StopIteration:
            product = Product(
                id=atomy_product['id'],
                name=atomy_product['name'],
                price=atomy_product['price'],
                points=atomy_product['points'],
                weight=0,
                available=atomy_product['available'],
                when_created=datetime.now()
            )
            new += 1
            db.session.add(product)
    print(f"Product synchronization result: same: {same}, new: {new}, modified: {modified}")
    db.session.commit()
