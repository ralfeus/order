import itertools
import json
import lxml.html
from lxml.cssselect import CSSSelector
from app import db
import re
import subprocess
import requests

def get_document_from_url(url, headers=None, raw_data=None, encoding='euc-kr'):
   
    headers_list = list(itertools.chain.from_iterable([
        ['-H', f"{k}: {v}"] for pair in headers for k,v in pair.items()
    ]))
    raw_data = ['--data-raw', raw_data] if raw_data else []
    output = subprocess.run([
        'c:\\Program Files\\Git\\mingw64\\bin\\curl.exe',
        url,
        '-v'
        ] + headers_list + raw_data,
        encoding=encoding, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    if re.search('HTTP.*? 200', output.stderr):
        doc = lxml.html.fromstring(output.stdout)
        return doc

    raise Exception(f"Couldn't get page {url}: " + output.stderr)
##############################################################
#########  Спроба ...  #######################################
def get_atomy_images():
    
    product_url = "https://www.atomy.kr/v2/Home/Product/GetShoopGoodsForImg"
    doc = get_document_from_url(product_url, headers=[{"content-type": "application/json"}],
        raw_data='{"GdsCode": "000333"}', encoding='utf8')
    data = json.loads(doc.text)
    result = []
    item_image_id = data['jsonData']['GdsCode']
    item_image_url = "https://static.atomy.com"+data['jsonData']['GdsImg1']
   
    for item in item_image_id:
      
        result.append({
            'image_id' : item_image_id,
            'image_url' : item_image_url
        })
    path_image, image_name = save_image(item_image_url)
    product_image(path_image, image_name)
    return result
##############################################################
def save_image(image_url):
    image_name = image_url.split('/')[-1]
    r = requests.get(image_url)
    path_image = '/static/images/products/' + image_name
    with open('D:/Projects/order/app/static/images/products/'+ image_name, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return path_image, image_name

def product_image(path_image, image_name):
    from app.products.models import Product
    from app.models.file import File
    
    products = Product.query.all()
    products.image = File(
        path = path_image,
        file_name = image_name)
    return path_image, image_name

if __name__ == '__main__':
    get_atomy_images()
    
