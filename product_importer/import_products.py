import json
import logging
import math
import sys
from typing import Any, Optional
from lxml import etree #type: ignore
from lxml.cssselect import CSSSelector
from tqdm import tqdm

from atomy import atomy_login2, set_language
from tools import get_html, get_json

sel_item = CSSSelector(".gdsList-wrap>li")
sel_rows_per_page = CSSSelector("[name=rowsPerPage]")
sel_total = CSSSelector('[name=totalCount]')
sel_item_code = CSSSelector(".gdImg>a")
sel_item_name = CSSSelector(".title")
sel_item_oos = CSSSelector(".gdInfo .state_tx>em")
sel_item_price = CSSSelector(".prc_ori>b")
sel_item_points = CSSSelector(".pv_ori>b")
sel_item_image_url = CSSSelector(".gdImg img")
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

def get_atomy_products(url_base: str, with_description: bool=False, socks5_proxy: Optional[str]=None) -> list[dict[str, Any]]:
    global URL_SUFFIX
    URL_SUFFIX = URL_SUFFIX.replace('ko-KR', 'en-KR')
    logger = logging.getLogger("get_atomy_products")
    jwt = atomy_login2('23426444', 'atomy#01', socks5_proxy)
    set_language('en', jwt, socks5_proxy)
    logger.info("Getting core products list")
    core_products = _get_products_list(url_base, jwt)
    logger.info("Got %s core products", len(core_products))
    result = []
    id_set = set()
    for core_product in tqdm(core_products):
        try:
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
            for to_add_item in to_add:
                if to_add_item['id'] not in id_set:
                    if with_description:
                        to_add_item['description'] = _get_description(to_add_item['id'], jwt, socks5_proxy)
                    result.append(to_add_item)
                    id_set.add(to_add_item['id'])
        except Exception as e:
            logger.warning(f"Couldn't add product {core_product}")
            logger.warning(str(e))

    return result

def _get_description(product_id: str, jwt: str, socks5_proxy: Optional[str] = None) -> str:
    result = get_html(f"{url_base}/product/{product_id}", 
                      headers=[{"Cookie": jwt}])
    description = result.cssselect('.product-detail-info')[0]
    return '\n'.join(description.itertext())

def _get_products_list(url_base: str, jwt:str='') -> list[dict[str, Any]]:
    url_template = "{}/search/searchGoodsList?sortType=POPULAR&pageIdx={}"
    products = []
    try:
        doc = get_html(
            url_template.format(url_base, 1), headers=[{"Cookie": jwt}]
        )
        total = int(sel_total(doc)[0].attrib['value'])
        rows_per_page = int(sel_rows_per_page(doc)[0].attrib['value'])
        pages = math.ceil(total / rows_per_page)
        for page in tqdm(range (1, pages + 1)):
            products_page = get_html(
                url_template.format(url_base, page),
                headers=[{"Cookie": jwt}],
            )
            products += _get_products(products_page)
        return products
    except Exception as ex:
        raise Exception(f"Couldn't get products list: {ex}")
    
def _get_products(products_page: etree.Element): #type: ignore
    return [{
        "id": sel_item_code(i)[0].attrib['href'].split('/')[-1],
        "atomy_id": sel_item_code(i)[0].attrib['href'].split('/')[-1],
        "name": ' '.join(sel_item_name(i)[0].itertext()),
        "name_english": ' '.join(sel_item_name(i)[0].itertext()),
        "price": sel_item_price(i)[0].text.replace(',', ''),
        "points": sel_item_points(i)[0].text.replace(',', ''),
        "available": len(sel_item_oos(i)) == 0,
        "image_url": 'https:' + sel_item_image_url(i)[0].attrib['src'],
        } for i in sel_item(products_page)
        if len(sel_item_price(i)) > 0
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
