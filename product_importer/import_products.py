from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import math
import sys
from typing import Any, Optional
from bs4 import BeautifulSoup
from tqdm import tqdm

from common.utils.atomy import atomy_login2, set_language
from common.utils import get_document, get_json

URL_SUFFIX = '_siteId=kr&_deviceType=pc&locale=ko-KR'

def get_atomy_images(item_code):
    product_url = (
        f"https://shop-api.atomy.com/svc/product/read?productId={item_code}"
        + "&_siteId=kr&_deviceType=pc&locale=en-KR"
    )
    result = get_json(product_url)
    image_url = result.get("item", {}).get("snsImage", {}).get("verticalThumbnailPc", "") \
        if isinstance(result, dict) else ""

    return image_url

def get_atomy_products(url_base: str, with_description: bool=False, 
                       socks5_proxy: str='', logger: logging.Logger=logging.root
                       ) -> list[dict[str, Any]]:
    global URL_SUFFIX
    URL_SUFFIX = URL_SUFFIX.replace('ko-KR', 'en-KR')
    jwt = atomy_login2('23426444', 'atomy#01', socks5_proxy)
    set_language('en', jwt, socks5_proxy)
    logger.info("Getting core products list")
    core_products = _get_products_list(url_base, jwt)
    logger.info("Got %s core products", len(core_products))
    result = []
    id_set = set()
    # Use ThreadPoolExecutor for better thread management
    max_workers = min(10, len(core_products))  # Limit concurrent threads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_product = {
            executor.submit(_get_product, core_product, url_base, jwt, 
                            with_description, id_set, logger, socks5_proxy): core_product
            for core_product in core_products
        }
        
        # Process results as they complete (immediate processing)
        for future in tqdm(as_completed(future_to_product), total=len(core_products), desc="Processing products"):
            core_product = future_to_product[future]
            try:
                processed_products = future.result()
                # Add processed products to result and update id_set
                for product in processed_products:
                    if product['id'] not in id_set:
                        result.append(product)
                        id_set.add(product['id'])
            except Exception as e:
                logger.warning(f"Error processing product {core_product.get('id', 'unknown')}: {e}")
    return result

def _get_product(core_product: dict[str, Any], url_base: str, jwt: str, 
                 with_description: bool, id_set: set,
                 logger: logging.Logger,
                 socks5_proxy: Optional[str]=None
                 ) -> list[dict[str, Any]]:
    """Process a single core product and return processed product data.
    
    Returns a list of processed products (usually 1, but can be multiple for products with options).
    """
    try:
        logger.info(f"Getting product options for {core_product['id']}")
        options = _get_product_options(core_product['id'], url_base)
        if len(options) == 1:
            to_add = [core_product]
        else:
            to_add = [{
                "id": i['materialCode'],
                "atomy_id": i['materialCode'],
                "name": i['itemNm'],
                "name_english": i['itemNm'],
                "price": i['custSalePrice'],
                "points": i['pvPrice'],
                "available": i['goodsStatNm'] == "goods.word.sale.normal",
                "image_url": core_product['image_url'],
            } for i in options]
        logger.info(f"Found {len(to_add)} products for {core_product['id']}")
        logger.info(f"Getting descriptions for {core_product['id']}")
        processed_products = []
        for to_add_item in to_add:
            if to_add_item['id'] not in id_set:
                if with_description:
                    desc_items = _get_description(
                        url_base, core_product['id'], jwt, socks5_proxy)
                    to_add_item['description'] = desc_items #TODO [0]
                processed_products.append(to_add_item)
        return processed_products
        
    except Exception as e:
        logger.warning(f"Couldn't process product {core_product.get('id', 'unknown')}")
        logger.warning(str(e))
        return []

def _get_description(url_base: str, product_id: str, jwt: str, 
                     socks5_proxy: Optional[str] = None) -> str:
    result = get_document(f"{url_base}/product/{product_id}", 
                      headers=[{"Cookie": jwt}])
    desc_element = result.select('.product-detail-info')[0]
    desc_html = desc_element.decode_contents()
    # description, metadata = convert_with_metadata(desc_html)
    #TODO: Extract image URLs from metadata and return them as well
    return desc_html #, [img['src'] for img in metadata.get('images', [])]

def _get_products_list(url_base: str, jwt:str='') -> list[dict[str, Any]]:
    url_template = "{}/search/searchGoodsList?sortType=POPULAR&pageIdx={}"
    products = []
    try:
        doc = get_document(
            url_template.format(url_base, 1), headers=[{"Cookie": jwt}]
        )
        total = int(str(doc.select('[name=totalCount]')[0]['value']))
        rows_per_page = int(str(doc.select('[name=rowsPerPage]')[0]['value']))
        pages = math.ceil(total / rows_per_page)
        for page in tqdm(range (1, pages + 1)):
            products_page = get_document(
                url_template.format(url_base, page),
                headers=[{"Cookie": jwt}],
            )
            products += _get_products(products_page)
        return products
    except Exception as ex:
        raise Exception(f"Couldn't get products list: {ex}")

def _get_products(products_page: BeautifulSoup):
    return [{
        "id": str(i.select(".gdImg>a")[0]['href']).split('/')[-1],
        "atomy_id": str(i.select(".gdImg>a")[0]['href']).split('/')[-1],
        "name": i.select(".title")[0].get_text(separator=' '),
        "name_english": i.select(".title")[0].get_text(separator=' '),
        "price": i.select(".prc_ori>b")[0].get_text().replace(',', ''),
        "points": i.select(".pv_ori>b")[0].get_text().replace(',', ''),
        "available": len(i.select(".gdInfo .state_tx>em")) == 0,
        "image_url": 'https:' + str(i.select(".gdImg img")[0]['src']).split('?')[0],
        } for i in products_page.select(".gdsList-wrap>li")
        if len(i.select(".prc_ori>b")) > 0
    ]

def _get_product_options(product_id, url_base: str, jwt:str='') -> list[dict[str, Any]]:
    options = get_json(
        f"{url_base}/goods/itemStatus",
        headers=[{"Cookie": jwt}, {"Content-Type": 'application/x-www-form-urlencoded'}],
        raw_data=f'goodsNo={product_id}&goodsTypeCd=101'
    )
    return list(options.values()) if isinstance(options, dict) else options

if __name__ == "__main__":
    url_base = sys.argv[1]
    print(json.dumps(get_atomy_products(url_base)))
