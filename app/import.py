import lxml.html
from lxml.cssselect import CSSSelector
import re
import subprocess

selItem = CSSSelector('td.line_C_r input[name=chk]')

def get_document_from_url(url, headers=None):
    headers_list = [
        header for set in list(map(
            lambda h: ['-H', f"{h}: {headers[h]}"], headers)) for header in set
    ]
    output = subprocess.run([
        'curl',
        url,
        '-v'
        ] + headers_list,
        encoding='euc-kr', stdout=subprocess.PIPE, check=False)

    doc = lxml.html.fromstring(output.stdout)
    return doc

def atomy():
    product_url = "https://www.atomy.kr/center/popup_material.asp"
    session = atomy_login()
    doc = get_document_from_url(product_url, {
        'Cookie': f"ASPSESSIONIDSCABDDBB={session}"})
    for item in selItem(doc):
        print(item.getparent().getparent())


def atomy_login():
    '''
    Logins to Atomy customer section
    '''
    output = subprocess.run([
        'curl',
        'https://www.atomy.kr/center/check_user.asp',
        '-H',
        'Referer: https://www.atomy.kr/center/login.asp?src=/center/c_sale_ins.asp',
        '--data-raw',
        'src=&admin_id=atomy1026&passwd=5714',
        '-v'
        ],
        encoding='euc-kr', stderr=subprocess.PIPE, check=False)
    if output.stderr.find('< location: ') != -1:
        return re.search(r'ASPSESSIONIDSCABDDBB=(\w+)', output.stderr).groups()[0]
    return None

if __name__ == '__main__':
    atomy()
