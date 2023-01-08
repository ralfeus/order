import itertools
import logging
import lxml.html
from lxml.cssselect import CSSSelector
import re
import subprocess

from app.tools import get_json

sel_item = CSSSelector('td.line_C_r input[name=chk]')
sel_item_code = CSSSelector('td.line_C_r:nth-child(2)')
sel_item_name = CSSSelector('td.line_L_r a')
sel_item_name_sold_out = CSSSelector('td.line_L_r a span')
sel_item_price = CSSSelector('td.line_C_r:nth-child(4)')
sel_item_points = CSSSelector('td.line_C_r:nth-child(5)')
sel_item_image_url = CSSSelector('ul.bxslider img.scr')

def get_document_from_url(url, headers=None, raw_data=None, encoding='euc-kr'):
    # headers_list = [
    #     header for set in list(map(
    #         lambda h: ['-H', f"{h}: {headers[h]}"], headers)) for header in set
    # ]
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data = ['--data-raw', raw_data] if raw_data else []
    output = subprocess.run([
        'curl',
        url,
        '-v'
        ] + headers_list + raw_data,
        encoding=encoding, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    if re.search('HTTP.*? 200', output.stderr):
        doc = lxml.html.fromstring(output.stdout)
        return doc

    raise Exception(f"Couldn't get page {url}: " + output.stderr)

def get_atomy_images(item_code):
    product_url = f"https://shop-api.atomy.com/svc/product/read?productId={item_code}" +\
        "&_siteId=kr&_deviceType=pc&locale=en-KR"
    result = get_json(product_url)
    image_url = '' if result.get('item') is None \
        else  result['item']['snsImage']['verticalThumbnailPc']
   
    return image_url

def get_atomy_products():
    logger = logging.getLogger("get_atomy_products")
    product_url = "https://www.atomy.kr/center/popup_material.asp"
    session_cookies = atomy_login()
    doc = get_document_from_url(product_url, 
        [{'Cookie': c} for c in session_cookies ])
    result = []
    items = sel_item(doc)
    for item in sel_item(doc):
        product_line = item.getparent().getparent()
        item_code = sel_item_code(product_line)[0].text.strip()
        logger.debug("Getting product %s", item_code)
        item_name = sel_item_name(product_line)[0].text.strip()
        item_image_url = get_atomy_images(item_code)
        item_sold_out_name_node = sel_item_name_sold_out(product_line)
        item_sold_out_name = item_sold_out_name_node[0].text.strip() \
                if item_sold_out_name_node and item_sold_out_name_node[0].text \
                else None
        item_price = re.sub('\D', '', sel_item_price(product_line)[0].text)
        item_points = re.sub('\D', '', sel_item_points(product_line)[0].text)
        if item_sold_out_name:
            item_name = item_sold_out_name
            item_available = False
        else:
            item_available = True
     
        result.append({
            'id': item_code,
            'name': item_name,
            'price': item_price,
            'points': item_points,
            'available': item_available,
            'image_url' : item_image_url
        })
    return result

def atomy_login(username='atomy1026', password='5714'):
    '''
    Logins to Atomy customer section
    '''
    output = subprocess.run([
        'curl',
        'https://www.atomy.kr/center/check_user.asp',
        '-H',
        'Referer: https://www.atomy.kr/center/login.asp?src=/center/c_sale_ins.asp',
        '--data-raw',
        f'src=&admin_id={username}&passwd={password}',
        '-v'
        ],
        encoding='euc-kr', stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=False)
    if re.search('< location: center_main', output.stderr):
        # return re.search(r'ASPSESSIONID(\w+)=(\w+)', output.stderr).group()
        return re.findall('set-cookie: (.*)', output.stderr)
    return None

if __name__ == '__main__':
    get_atomy_products()
      