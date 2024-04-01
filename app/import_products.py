import itertools
import logging
from typing import Any
import lxml.html
from lxml.cssselect import CSSSelector
import re
import subprocess

from tqdm import tqdm

from app.tools import get_json
from app.utils.atomy import URL_BASE, URL_SUFFIX, atomy_login2

sel_item = CSSSelector("td.line_C_r input[name=chk]")
sel_item_code = CSSSelector("td.line_C_r:nth-child(2)")
sel_item_name = CSSSelector("td.line_L_r a")
sel_item_name_sold_out = CSSSelector("td.line_L_r a span")
sel_item_price = CSSSelector("td.line_C_r:nth-child(4)")
sel_item_points = CSSSelector("td.line_C_r:nth-child(5)")
sel_item_image_url = CSSSelector("ul.bxslider img.scr")


def get_document_from_url(url, headers=None, raw_data=None, encoding="euc-kr"):
    headers_list = list(
        itertools.chain.from_iterable(
            [["-H", f"{k}: {v}"] for pair in headers for k, v in pair.items()]
        )
    )
    raw_data = ["--data-raw", raw_data] if raw_data else []
    output = subprocess.run(
        ["curl", url, "-v"] + headers_list + raw_data,
        encoding=encoding,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if re.search("HTTP.*? 200", output.stderr):
        doc = lxml.html.fromstring(output.stdout)
        return doc

    raise Exception(f"Couldn't get page {url}: " + output.stderr)


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
        if core_product["materialCode"] is None:
            continue
        if core_product["optionType"]["value"] == "none":
            result.append(
                {
                    "id": core_product["materialCode"],
                    "atomy_id": core_product["id"],
                    "name": core_product["productName"],
                    "name_english": core_product['name'],
                    "price": core_product["memRetailPrice"],
                    "points": core_product["pvPrice"],
                    "available": "soldOut" not in core_product["flags"],
                    "image_url": core_product["images"][0]["file"] 
                        if len(core_product['images']) > 0 else '',
                }
            )
        else:
            result += [
                {
                    "id": p["materialCode"],
                    "atomy_id": p["id"],
                    "name": f'{core_product["productName"]} - {p["name"]}',
                    "name_english": f'{core_product["name"]} - {p["name"]}',
                    "price": p["memRetailPrice"],
                    "points": p["pvPrice"],
                    "available": p['enable'] and not p['soldOut'],
                    "image_url": core_product["images"][0]["file"] 
                        if len(core_product['images']) > 0 else '',
                }
                for p in _get_product_options(core_product, jwt)
            ]

    return result


def _get_products_list(jwt):
    url_template = "{}/product/list?page={}&{}"
    products = []
    products_pre_get = get_json(
        url_template.format(URL_BASE, 1, URL_SUFFIX), headers=[{"Cookie": jwt}]
    )
    if products_pre_get["result"] != "200":
        raise products_pre_get["resultMessage"]
    pages = products_pre_get["pageCount"]
    for page in tqdm(range (1, pages + 1)):
        products_page = get_json(
            url_template.format(URL_BASE, page, URL_SUFFIX),
            headers=[{"Cookie": jwt}],
        )
        if products_page["result"] != "200":
            raise products_page["resultMessage"]
        products += products_page['items']
    return products


def _get_product_options(product, jwt):
    options = get_json(
        f"{URL_BASE}/product/optionsOnly?productId={product['id']}&{URL_SUFFIX}",
        headers=[{"Cookie": jwt}]
    )
    if options['result'] != '200':
        raise options['resultMessage']
    return [o for o in options['item']['option']['productOptions']]

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
