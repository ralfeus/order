import logging
import math
from typing import Any
from lxml import etree
from lxml.cssselect import CSSSelector
import re
import subprocess
from tqdm import tqdm

from app.tools import get_html, get_json
from exceptions import HTTPError

from utils.atomy import URL_BASE, URL_SUFFIX, atomy_login2

sel_item = CSSSelector(".gdsList-wrap>li")
sel_rows_per_page = CSSSelector("[name=rowsPerPage]")
sel_total = CSSSelector('[name=totalCount]')
sel_item_code = CSSSelector(".gdImg>a")
sel_item_name = CSSSelector(".title")
sel_item_oos = CSSSelector(".gdInfo .state_tx>em")
sel_item_price = CSSSelector(".prc_ori>b")
sel_item_points = CSSSelector(".pv_ori>b")
sel_item_image_url = CSSSelector(".gdImg img")


# def get_document_from_url(url, headers=None, raw_data=None, encoding="euc-kr"):
#     headers_list = list(
#         itertools.chain.from_iterable(
#             [["-H", f"{k}: {v}"] for pair in headers for k, v in pair.items()]
#         )
#     )
#     raw_data = ["--data-raw", raw_data] if raw_data else []
#     output = subprocess.run(
#         ["curl", url, "-v"] + headers_list + raw_data,
#         encoding=encoding,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         check=False,
#     )

#     if re.search("HTTP.*? 200", output.stderr):
#         doc = lxml.html.fromstring(output.stdout)
#         return doc

#     raise Exception(f"Couldn't get page {url}: " + output.stderr)


def get_atomy_images(item_code):
    product_url = (
        f"https://shop-api.atomy.com/svc/product/read?productId={item_code}"
        + "&_siteId=kr&_deviceType=pc&locale=en-KR"
    )
    result = get_json(product_url)
    image_url = (
        ""
        if result.get("item") is None
        else result["item"]["snsImage"]["verticalThumbnailPc"]
    )

    return image_url


def get_atomy_products() -> list[dict[str, Any]]:
    global URL_SUFFIX
    URL_SUFFIX = URL_SUFFIX.replace('ko-KR', 'en-KR')
    logger = logging.getLogger("get_atomy_products")
    jwt = atomy_login2("S5832131", "mkk03020529!!")
    logger.info("Getting core products list")
    core_products = _get_products_list(jwt)
    logger.info("Got %s core products", len(core_products))
    result = []
    for core_product in tqdm(core_products):
        options = _get_product_options(core_product['id'], jwt)
        result += [core_product] if len(options) == 1 \
        else [{
            "id": i['materialCode'],
            "atomy_id": i['materialCode'],
            "name": i['itemNm'],
            "name_english": i['itemNm'],
            "price": i['custSalePrice'],
            "points": i['pvPrice'],
            "available": i['goodsStatNm'] == "goods.word.sale.normal",
            "image_url": core_product['image_url'],
        } for i in options]
        

    return result

def _get_products_list(jwt):
    url_template = "{}/search/searchGoodsList?sortType=POPULAR&pageIdx={}"
    products = []
    try:
        doc = get_html(
            url_template.format(URL_BASE, 1), headers=[{"Cookie": jwt}]
        )
        total = int(sel_total(doc)[0].attrib['value'])
        rows_per_page = int(sel_rows_per_page(doc)[0].attrib['value'])
        pages = math.ceil(total / rows_per_page)
        for page in tqdm(range (1, pages + 1)):
            products_page = get_html(
                url_template.format(URL_BASE, page),
                headers=[{"Cookie": jwt}],
            )
            products += _get_products(products_page)
        return products
    except HTTPError as ex:
        raise Exception(f"Couldn't get products list: {ex}")
    
def _get_products(products_page: etree.Element): #type: ignore
    return [{
        "id": sel_item_code(i)[0].attrib['href'].split('/')[-1],
        "atomy_id": sel_item_code(i)[0].attrib['href'].split('/')[-1],
        "name": sel_item_name(i)[0].text,
        "name_english": sel_item_name(i)[0].text,
        "price": sel_item_price(i)[0].text.replace(',', ''),
        "points": sel_item_points(i)[0].text.replace(',', ''),
        "available": len(sel_item_oos(i)) == 0,
        "image_url": 'https:' + sel_item_image_url(i)[0].attrib['src'],
        } for i in sel_item(products_page)
        if len(sel_item_price(i)) > 0
    ]


def _get_product_options(product_id, jwt):
    options = get_json(
        f"{URL_BASE}/goods/itemStatus",
        headers=[{"Cookie": jwt}, {"Content-Type": 'application/x-www-form-encoded'}],
        raw_data=f'goodsNo={product_id}&goodsTypeCd=101'
    )
    return options.values()

def atomy_login(username="atomy1026", password="5714"):
    """
    Logins to Atomy customer section
    """
    output = subprocess.run(
        [
            "curl",
            "https://www.atomy.kr/center/check_user.asp",
            "-H",
            "Referer: https://www.atomy.kr/center/login.asp?src=/center/c_sale_ins.asp",
            "--data-raw",
            f"src=&admin_id={username}&passwd={password}",
            "-v",
        ],
        encoding="euc-kr",
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        check=False,
    )
    if re.search("< location: center_main", output.stderr):
        # return re.search(r'ASPSESSIONID(\w+)=(\w+)', output.stderr).group()
        return re.findall("set-cookie: (.*)", output.stderr)
    return None


if __name__ == "__main__":
    get_atomy_products()
