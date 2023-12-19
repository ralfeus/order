from datetime import datetime
from celery.utils.log import get_task_logger
import logging
import requests
from sqlalchemy.sql.elements import Null
from tqdm import tqdm
from app.models.file import File
from app import celery, db

@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(28800, import_products,
        name="Import products from Atomy every 8 hours")

@celery.task
def import_products():
    from app.import_products import get_atomy_products
    from app.products.models import Product
    
    logger = get_task_logger('import_products')
    logger.info("Starting products import")
    products = Product.query.all()
    same = new = modified = ignored = 0
    vendor_products = get_atomy_products()
    try:
        db.session.commit()
    except:
        db.session.rollback()
    logger.info("Got %d products", len(vendor_products))
    if len(vendor_products) == 0: # Something went wrong
        logger.warning("Something went wrong. Didn't get any products from vendor. Exiting...")
        return
    for atomy_product in vendor_products:
        try:
            product = next(p for p in products
                           if p.id.lstrip('0') == atomy_product['id'].lstrip('0'))
            if product.synchronize:
                logger.debug('Synchronizing product %s', atomy_product['id'])
                is_dirty = False
                if product.name != atomy_product['name']:
                    logger.debug('\tname(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['name'], product.name)
                    product.name = atomy_product['name']
                    is_dirty = True
                if product.price != int(atomy_product['price']):
                    logger.debug('\tprice(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['price'], product.price)
                    product.price = int(atomy_product['price'])
                    is_dirty = True
                if product.points != int(atomy_product['points']):
                    logger.debug('\tpoints(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['points'], product.points)
                    product.points = int(atomy_product['points'])
                    is_dirty = True
                if product.available != atomy_product['available']:
                    logger.debug('\tavailable(%s): vendor(%s) != local(%s)', 
                        atomy_product['id'], atomy_product['available'], product.available)
                    product.available = atomy_product['available']
                    is_dirty = True
                if product.image is None:
                    path_image, image_name = save_image(atomy_product['image_url'])
                    product.image = File(
                        path = path_image,
                        file_name = image_name)
                    is_dirty = True
                if is_dirty:
                    logger.debug('\t%s: MODIFIED', atomy_product['id'])
                    product.when_changed = datetime.now()
                    modified += 1
                else:
                    logger.debug('\t%s: SAME', atomy_product['id'])
                    same += 1
            else:
                logger.debug('\t%s: IGNORED', product.id)
                ignored += 1

            products.remove(product)
        except StopIteration:
            logger.debug('%s: No local product found. ADDING', atomy_product['id'])
            path_image, image_name = save_image(atomy_product['image_url'])
            product = Product(
                id=atomy_product['id'],
                vendor_id=atomy_product['atomy_id'],
                name=atomy_product['name'],
                price=atomy_product['price'],
                points=atomy_product['points'],
                weight=0,
                available=atomy_product['available'],
                when_created=datetime.now(),
                image=File(
                    path=path_image,
                    file_name=image_name)
            )
            new += 1
            try:
                db.session.add(product)
            except:
                logger.exception("error")
    logger.debug('%d local products left without matching vendor\'s ones. Will be disabled',
        len(products))
    for product in products:
        if product.synchronize:
            logger.debug("%s: should be synchronized. DISABLED", product.id)
            product.available = False
            modified += 1
        else:
            logger.debug("%s: should NOT be synchronized. IGNORED", product.id)
            ignored += 1
    logger.info(
        "Product synchronization result: same: %d, new: %d, modified: %d, ignored: %d",
        same, new, modified, ignored)
    db.session.commit()

@celery.task
def add_together(a, b):
#    for i in range(100):
#        sleep(1)
    return a + b


def save_image(image_url):
    from flask import current_app
    if image_url!='':
        image_name = image_url.split('/')[-1]
        r = requests.get(image_url)
        path_image = '/upload/products/' + image_name
        with open(current_app.root_path + '/upload/products/'+ image_name, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
    else:
        image_name=''
        path_image=''
    return path_image, image_name
