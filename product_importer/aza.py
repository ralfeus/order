'''Imports products from AtomyAza (atomyaza.co.kr)'''
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import re
from typing import Any, Callable, Iterable, Optional

from bs4 import BeautifulSoup, Tag
import requests
from tqdm import tqdm

from common.utils.aza import URL_BASE, TIMEOUT, AzaLoginError, aza_login

VENDOR = 'AtomyAza'
LIST_ROWS = 500
MAX_PAGES = 1000
NAME_LENGTH = 256
OPTION_SEPARATOR = chr(30)

class GroupProductError(Exception):
    '''Raised for group products. They are showcases of other products,
    which are listed separately'''

def get_aza_products(username: str, password: str, categories: Iterable[str],
                     socks5_proxy: str='', logger: logging.Logger=logging.root,
                     max_workers: int=5,
                     login: Callable[..., requests.Session]=aza_login
                     ) -> list[dict[str, Any]]:
    '''Returns products of the provided AtomyAza categories.
    A category can be either top level (3 digits) or leaf (6 digits) ca_id.
    Products with several options are returned as one product per option.

    Raises AzaLoginError if the session isn't authenticated at any point,
    so partial results never get to synchronization'''
    categories = [c.strip() for c in categories if c.strip()]
    if not categories:
        logger.info("No AtomyAza categories are configured. Nothing to import")
        return []
    session = login(username, password, socks5_proxy)
    ca_ids = resolve_categories(categories, get_categories(session), logger)
    if not ca_ids:
        logger.warning("None of configured categories %s exist at AtomyAza", categories)
        return []

    cards: dict[str, dict[str, Any]] = {}
    for ca_id in ca_ids:
        logger.info("Getting products list of category %s", ca_id)
        category_cards = _get_products_list(session, ca_id)
        logger.info("Got %d products in category %s", len(category_cards), ca_id)
        for card in category_cards:
            cards.setdefault(card['gs_id'], card)
    logger.info("Got %d unique products", len(cards))

    result = []
    if not cards:
        return result
    with ThreadPoolExecutor(max_workers=min(max_workers, len(cards))) as executor:
        future_to_card = {
            executor.submit(_get_product, session, card): card
            for card in cards.values()
        }
        for future in tqdm(as_completed(future_to_card), total=len(future_to_card),
                           desc="Processing products"):
            card = future_to_card[future]
            try:
                result += future.result()
            except AzaLoginError:
                for pending in future_to_card:
                    pending.cancel()
                raise
            except GroupProductError:
                logger.info("Skipping group product %s", card['gs_id'])
            except Exception as ex:
                logger.warning("Couldn't process product %s: %s", card['gs_id'], ex)
    return result

def get_categories(session: requests.Session) -> list[dict[str, Any]]:
    '''Returns AtomyAza categories tree as a flat list of
    {ca_id, name, parent} taken from the category menu'''
    doc = _get_document(session, f'{URL_BASE}/m/')
    categories = []
    for top in doc.select('div.category__depth1'):
        leaves = [
            (m.group(1), str(a.get_text(strip=True)))
            for a in top.select('div.category__depth2 a[href*="ca_id="]')
            if (m := re.search(r'ca_id=(\d+)', str(a['href'])))
        ]
        if not leaves:
            continue
        top_id = leaves[0][0][:3]
        title = top.select_one('.category__depth1__tit span')
        categories.append({
            'ca_id': top_id,
            'name': title.get_text(strip=True) if title else top_id,
            'parent': None
        })
        categories += [{'ca_id': ca_id, 'name': name, 'parent': top_id}
                       for ca_id, name in leaves]
    return categories

def resolve_categories(configured: Iterable[str], tree: list[dict[str, Any]],
                       logger: logging.Logger) -> list[str]:
    '''Returns configured category IDs existing in the tree.
    Categories covered by already selected parent ones are omitted
    because the site matches categories by prefix'''
    existing = {c['ca_id'] for c in tree}
    requested = list(dict.fromkeys(c.strip() for c in configured if c.strip()))
    unknown = [c for c in requested if c not in existing]
    if unknown:
        logger.warning("Unknown AtomyAza categories are ignored: %s", ', '.join(unknown))
    known = [c for c in requested if c in existing]
    return [c for c in known
            if not any(c != other and c.startswith(other) for other in known)]

def _get_document(session: requests.Session, url: str,
                  params: Optional[dict[str, Any]]=None) -> BeautifulSoup:
    response = session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')

def _get_products_list(session: requests.Session, ca_id: str) -> list[dict[str, Any]]:
    '''Returns product cards of a category (including subcategories)'''
    cards = []
    for page in range(1, MAX_PAGES + 1):
        response = session.get(
            f'{URL_BASE}/m/shop/ajax.list.php',
            params={'ca_id': ca_id, 'sort': '', 'sortodr': '', 'stx': '',
                    'page': page, 'rows': LIST_ROWS},
            timeout=TIMEOUT)
        response.raise_for_status()
        result = response.json()
        page_cards = _parse_cards(BeautifulSoup(result.get('str') or '', 'html.parser'))
        cards += page_cards
        # The last page is returned with err=1 along with its products
        if str(result.get('err')) == '1' or not page_cards:
            break
    return cards

def _parse_cards(doc: BeautifulSoup) -> list[dict[str, Any]]:
    '''Parses product cards of a products list.
    Price is None when the product is sold out'''
    if doc.select_one('.product-item .memopen'):
        raise AzaLoginError("Products list is shown for anonymous user")
    cards = []
    for item in doc.select('div.product-item[data-product-id]'):
        title = item.select_one('.product-item__title')
        image = item.select_one('.product-item__image img')
        price = item.select_one('.product-item__price .mpr')
        points = item.select_one('.product-item__pv__number')
        cards.append({
            'gs_id': str(item['data-product-id']),
            'name': title.get_text(strip=True) if title else '',
            'price': _to_int(price.get_text()) if price else None,
            'points': _to_int(points.get_text()) if points else None,
            'available': item.select_one('.soldout') is None,
            'image_url': _normalize_url(str(image['src'])) if image else ''
        })
    return cards

def _get_product(session: requests.Session, card: dict[str, Any]
                 ) -> list[dict[str, Any]]:
    doc = _get_document(session, f'{URL_BASE}/m/shop/view.php',
                        params={'gs_id': card['gs_id']})
    return _parse_product(card, doc, session)

def _parse_product(card: dict[str, Any], doc: BeautifulSoup,
                   session: Optional[requests.Session]=None) -> list[dict[str, Any]]:
    '''Makes products out of product page. Each option of a product
    with several options becomes a separate product'''
    if re.search(r'tb_is_member\s*=\s*"0"', str(doc)):
        raise AzaLoginError("Product page is shown for anonymous user")
    title = doc.select_one('.view_head_wrap .subject strong')
    name = title.get_text(strip=True) if title else card['name']
    options = _get_options(session, card['gs_id'], doc)
    base = {
        'vendor': VENDOR,
        'vendor_id': card['gs_id'],
        'name': name[:NAME_LENGTH],
        'price': card['price'],
        'points': card['points'],
        'available': card['available'],
        'image_url': card['image_url']
    }
    if len(options) == 0:
        return [base]
    if len(options) == 1:
        return [{**base,
            'price': options[0]['price'],
            'points': options[0]['points'],
            'available': card['available'] and options[0]['available']
        }]
    return [{**base,
        'vendor_id': f"{card['gs_id']}:{option['id']}",
        'name': f"{name} - {option['name']}"[:NAME_LENGTH],
        'price': option['price'],
        'points': option['points'],
        'available': option['available']
    } for option in options]

def _get_options(session: Optional[requests.Session], gs_id: str,
                 doc: BeautifulSoup) -> list[dict[str, Any]]:
    '''Returns all purchasable option combinations of a product.
    Only the first option level is on the product page. Lower levels are
    loaded by the selected upper level values like the site does'''
    if doc.select_one('[data-grp_item]'):
        raise GroupProductError("Group product is a showcase of other products")
    levels = [str(a.get('data-value', '')) for a in doc.select('.opt_href')]
    if len(levels) <= 1:
        return [_parse_option(li) for li in doc.select('li.opt_list_li[data-value]')]
    if session is None:
        raise ValueError("Session is required to load lower option levels")
    top_values = [str(li['data-value'])
                  for li in doc.select('#opt_list0 li.opt_list_li[data-value]')]
    return _get_lower_options(session, gs_id, top_values, '', 0, levels)

def _get_lower_options(session: requests.Session, gs_id: str, values: list[str],
                       parent_path: str, level: int, levels: list[str]
                       ) -> list[dict[str, Any]]:
    options = []
    for value in values:
        # The site identifies selection by values of all upper levels joined by chr(30)
        path = value if not parent_path or value.startswith(parent_path + OPTION_SEPARATOR) \
            else parent_path + OPTION_SEPARATOR + value
        response = session.post(
            f'{URL_BASE}/m/shop/view_option.new.php',
            data={'gs_id': gs_id, 'opt_id': path, 'idx': level,
                  'sel_count': len(levels), 'opt_title': levels[level + 1]},
            headers={'X-Requested-With': 'XMLHttpRequest'},
            timeout=TIMEOUT)
        response.raise_for_status()
        items = BeautifulSoup(response.text, 'html.parser') \
            .select('li.opt_list_li[data-value]')
        if level + 2 < len(levels):
            options += _get_lower_options(
                session, gs_id, [str(li['data-value']) for li in items],
                path, level + 1, levels)
        else:
            options += [_parse_option(li) for li in items]
    return options

def _parse_option(li: Tag) -> dict[str, Any]:
    '''Option's data-value is "name,additional price,stock,base price,PV,option ID".
    The name may contain commas. Names of multi-level options are values of
    all levels joined by chr(30)'''
    name, add_price, stock, base_price, points, option_id = \
        str(li['data-value']).rsplit(',', 5)
    return {
        'id': option_id.strip(),
        'name': ' / '.join(part.strip() for part in name.split(OPTION_SEPARATOR)),
        'price': int(base_price) + int(add_price),
        'points': int(points),
        'available': li.get('data-possible') == '1' and int(stock) > 0
    }

def _to_int(text: str) -> int:
    return int(re.sub(r'[^\d]', '', text) or 0)

def _normalize_url(url: str) -> str:
    url = url.split('?')[0]
    return 'https:' + url if url.startswith('//') else url
