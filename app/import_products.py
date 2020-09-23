import lxml.html
from lxml.cssselect import CSSSelector
import re
import subprocess

sel_item = CSSSelector('td.line_C_r input[name=chk]')
sel_item_code = CSSSelector('td.line_C_r:nth-child(2)')
sel_item_name = CSSSelector('td.line_L_r a')
sel_item_name_sold_out = CSSSelector('td.line_L_r a span')
sel_item_price = CSSSelector('td.line_C_r:nth-child(4)')
sel_item_points = CSSSelector('td.line_C_r:nth-child(5)')

def get_document_from_url(url, headers=None):
    headers_list = [
        header for set in list(map(
            lambda h: ['-H', f"{h}: {headers[h]}"], headers)) for header in set
    ]
    output = subprocess.run([
        '/usr/bin/curl',
        url,
        '-v'
        ] + headers_list,
        encoding='euc-kr', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    doc = lxml.html.fromstring(output.stdout)
    return doc

def atomy():
    product_url = "https://www.atomy.kr/center/popup_material.asp"
    session = atomy_login()
    doc = get_document_from_url(product_url, {
        'Cookie': session })
    for item in sel_item(doc):
        product_line = item.getparent().getparent()
        item_code = sel_item_code(product_line)[0].text.strip()
        item_name = sel_item_name(product_line)[0].text.strip()
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
        yield {
            'id': item_code,
            'name': item_name,
            'price': item_price,
            'points': item_points,
            'available': item_available
        }

def atomy_login():
    '''
    Logins to Atomy customer section
    '''
    output = subprocess.run([
        '/usr/bin/curl',
        'https://www.atomy.kr/center/check_user.asp',
        '-H',
        'Referer: https://www.atomy.kr/center/login.asp?src=/center/c_sale_ins.asp',
        '--data-raw',
        'src=&admin_id=atomy1026&passwd=5714',
        '-v'
        ],
        encoding='euc-kr', stderr=subprocess.PIPE, stdout=subprocess.PIPE, check=False)
    if output.stderr.find('< location: ') != -1:
        return re.search(r'ASPSESSIONID(\w+)=(\w+)', output.stderr).group()
    return None

if __name__ == '__main__':
    atomy()
