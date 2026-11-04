from datetime import datetime
import logging
import re
from typing import Any, Iterable
from celery.utils.log import get_task_logger
import os
import requests
from tqdm import tqdm
from app.models.file import File
from app import celery, db
from common.utils.atomy import URL_BASE
from common.utils.aza import AzaLoginError
from product_importer import get_atomy_products
from product_importer.aza import VENDOR as AZA_VENDOR, get_aza_products

IMAGE_TIMEOUT = 30
AZA_IMPORT_PERIOD = 86400
AZA_CATEGORIES_SETTING = 'product_import.aza.categories'

@celery.on_after_finalize.connect #type: ignore
def setup_periodic_tasks(sender, **kwargs):
    from flask import current_app
    sender.add_periodic_task(28800, import_products,
        name="Import products from Atomy every 8 hours")
    sender.add_periodic_task(
        current_app.config.get('AZA_IMPORT_PERIOD', AZA_IMPORT_PERIOD),
        import_aza_products, name="Import products from AtomyAza")

@celery.task
def import_products():
    from flask import current_app

    logger = get_task_logger('import_products')
    logger.info("Starting products import")
    vendor_products = get_atomy_products(
        current_app.config.get('PRODUCT_IMPORT_URL', URL_BASE), logger=logger)
    try:
        db.session.commit() #type: ignore
    except:
        db.session.rollback() #type: ignore
    logger.info("Got %d products", len(vendor_products))
    _sync_products('Atomy', [{
        **atomy_product, 'vendor_id': atomy_product['atomy_id']
    } for atomy_product in vendor_products], logger)

@celery.task
def import_aza_products():
    '''Imports products of AtomyAza categories set by admin'''
    from flask import current_app
    from app.settings.models.setting import Setting

    logger = get_task_logger('import_aza_products')
    categories = [c for c in re.split(r'[\s,]+', Setting.get(AZA_CATEGORIES_SETTING) or '')
                  if c]
    db.session.commit() # Don't hold the transaction during long import
    if not categories:
        logger.info("No AtomyAza categories are set in <%s>. Nothing to import",
                    AZA_CATEGORIES_SETTING)
        return
    username = current_app.config.get('AZA_LOGIN')
    password = current_app.config.get('AZA_PASSWORD')
    if not username or not password:
        logger.error("AZA_LOGIN and AZA_PASSWORD must be configured to import AtomyAza products")
        return
    logger.info("Starting AtomyAza products import of categories %s", categories)
    try:
        vendor_products = get_aza_products(
            username, password, categories,
            socks5_proxy=current_app.config.get('AZA_SOCKS5_PROXY', ''), logger=logger)
    except AzaLoginError as ex:
        logger.error("Couldn't import AtomyAza products: %s", ex)
        return
    logger.info("Got %d products", len(vendor_products))
    _sync_products(AZA_VENDOR, [{**vendor_product, 'id': vendor_product['vendor_id']}
                                for vendor_product in vendor_products], logger)

def _sync_products(vendor: str, vendor_products: Iterable[dict[str, Any]],
                   logger: logging.Logger=logging.root):
    '''Synchronizes local products of the vendor with the vendor's catalog.
    Each vendor product has "id", "vendor_id", "name", "price", "points",
    "available" and "image_url". Unknown price or points (None) keep local values.
    Local products of the vendor missing in the catalog are disabled.
    Products of other vendors aren't touched'''
    from app.products.models import Product

    vendor_products = list(vendor_products)
    if len(vendor_products) == 0: # Something went wrong
        logger.warning("Something went wrong. Didn't get any products from vendor %s. Exiting...",
                       vendor)
        return
    id_length = Product.__table__.c.id.type.length
    local_products = {}
    # Local duplicates ('247' and '000247') beyond the first one are disabled
    local_duplicates = []
    for product in Product.query.filter_by(vendor=vendor):
        if local_products.setdefault(_normalize_id(product.id), product) is not product:
            local_duplicates.append(product)
    processed = set()
    same = new = modified = ignored = 0
    for vendor_product in tqdm(vendor_products):
        product_id = vendor_product['id']
        if len(product_id) > id_length:
            logger.warning("%s: product ID is longer than %d characters. SKIPPED",
                           product_id, id_length)
            continue
        if _normalize_id(product_id) in processed:
            logger.debug('%s: duplicate in the catalog. SKIPPED', product_id)
            continue
        processed.add(_normalize_id(product_id))
        product = local_products.pop(_normalize_id(product_id), None)
        if product is None:
            logger.debug('%s: No local product found. ADDING', product_id)
            db.session.add(Product( #type: ignore
                id=product_id,
                vendor=vendor,
                vendor_id=vendor_product['vendor_id'],
                name=vendor_product['name'],
                price=vendor_product['price'] or 0,
                points=vendor_product['points'] or 0,
                weight=0,
                available=vendor_product['available'],
                when_created=datetime.now(),
                image=_get_image(vendor_product['image_url'], logger)
            ))
            new += 1
        elif product.synchronize:
            if _update_product(product, vendor_product, logger):
                logger.debug('\t%s: MODIFIED', product_id)
                product.when_changed = datetime.now()
                modified += 1
            else:
                logger.debug('\t%s: SAME', product_id)
                same += 1
        else:
            logger.debug('\t%s: IGNORED', product.id)
            ignored += 1
    logger.debug('%d local products left without matching vendor\'s ones. Will be disabled',
        len(local_products) + len(local_duplicates))
    for product in [*local_products.values(), *local_duplicates]:
        if product.synchronize:
            logger.debug("%s: should be synchronized. DISABLED", product.id)
            product.available = False
            modified += 1
        else:
            logger.debug("%s: should NOT be synchronized. IGNORED", product.id)
            ignored += 1
    logger.info(
        "Product synchronization result of %s: same: %d, new: %d, modified: %d, ignored: %d",
        vendor, same, new, modified, ignored)
    db.session.commit() #type: ignore

def _normalize_id(product_id: str) -> str:
    '''Product IDs may come with or without leading zeroes ('247' vs '000247').
    Normalized form is used to treat them as the same product.'''
    return product_id.lstrip('0') or '0'

def _update_product(product, vendor_product: dict[str, Any], logger: logging.Logger) -> bool:
    '''Updates local product with vendor's data. Returns whether anything changed'''
    logger.debug('Synchronizing product %s', product.id)
    is_dirty = False
    for attribute in ['vendor_id', 'name', 'price', 'points', 'available']:
        value = vendor_product[attribute]
        if value is None:
            continue
        if attribute in ('price', 'points'):
            value = int(value)
        if getattr(product, attribute) != value:
            logger.debug('\t%s(%s): vendor(%s) != local(%s)',
                attribute, product.id, value, getattr(product, attribute))
            setattr(product, attribute, value)
            is_dirty = True
    if product.image is None:
        product.image = _get_image(vendor_product['image_url'], logger)
        is_dirty = is_dirty or product.image is not None
    return is_dirty

def _get_image(image_url: str, logger: logging.Logger):
    '''Downloads product image. Returns None if it can't be downloaded,
    so it's retried during next synchronization'''
    try:
        path_image, image_name = save_image(image_url)
    except Exception as ex:
        logger.warning("Couldn't download image %s: %s", image_url, ex)
        return None
    return File(path=path_image, file_name=image_name)

def save_image(image_url):
    if image_url != '':
        from app.tools import get_products_path
        image_name = image_url.split('/')[-1]
        r = requests.get(image_url, timeout=IMAGE_TIMEOUT)
        r.raise_for_status()
        products_dir = get_products_path()
        os.makedirs(products_dir, exist_ok=True)
        with open(os.path.join(products_dir, image_name), 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        path_image = '/products/' + image_name
    else:
        image_name = ''
        path_image = ''
    return path_image, image_name
