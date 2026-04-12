#!/usr/bin/env python3
"""Create test shipments at ECmgmt via the public API, simulating OM calls.

Usage:
    python scripts/create_test_shipments.py [--url URL] [--carrier CODE] [--count N]

Examples:
    python scripts/create_test_shipments.py
    python scripts/create_test_shipments.py --url http://localhost:8000 --carrier DHL --count 5
"""
import argparse
import random
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    sys.exit('requests is not installed. Run: pip install requests')

# ---------------------------------------------------------------------------
# Test data pools
# ---------------------------------------------------------------------------

FIRST_NAMES = ['Anna', 'Lukas', 'Sophie', 'Max', 'Emma', 'Felix', 'Laura', 'Jonas']
LAST_NAMES  = ['Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber', 'Meyer', 'Wagner']

ADDRESSES = [
    ('Unter den Linden 1',  'Berlin',   'DE', '10117'),
    ('Marienplatz 5',       'Munich',   'DE', '80331'),
    ('Zeil 106',            'Frankfurt','DE', '60313'),
    ('Königsallee 30',      'Düsseldorf','DE','40212'),
    ('Jungfernstieg 10',    'Hamburg',  'DE', '20354'),
    ('Prager Straße 8',     'Dresden',  'DE', '01069'),
    ('Hohe Straße 1',       'Cologne',  'DE', '50667'),
]

BOXES = [
    {'weight_kg': '0.500', 'length_cm': '20.0', 'width_cm': '15.0', 'height_cm': '10.0'},
    {'weight_kg': '1.200', 'length_cm': '30.0', 'width_cm': '20.0', 'height_cm': '15.0'},
    {'weight_kg': '2.800', 'length_cm': '40.0', 'width_cm': '30.0', 'height_cm': '20.0'},
    {'weight_kg': '5.000', 'length_cm': '50.0', 'width_cm': '40.0', 'height_cm': '30.0'},
    {'weight_kg': '0.300'},  # no dimensions — weight only
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_name() -> str:
    return f'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'


def random_email(name: str) -> str:
    local = name.lower().replace(' ', '.').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe')
    return f'{local}@example.com'


def random_phone() -> str:
    return f'+49{random.randint(1510000000, 1799999999)}'


def make_order_id(seq: int) -> str:
    ts = datetime.now().strftime('%Y%m%d')
    return f'TEST-{ts}-{seq:04d}'


def create_shipment(base_url: str, carrier: str, seq: int) -> dict:
    name = random_name()
    address, city, country, zip_code = random.choice(ADDRESSES)
    box = random.choice(BOXES)

    payload = {
        'order_id':         make_order_id(seq),
        'customer_name':    name,
        'email':            random_email(name),
        'address':          address,
        'city':             city,
        'country':          country,
        'zip':              zip_code,
        'phone':            random_phone(),
        'shipment_type_code': carrier,
        **box,
    }

    resp = requests.post(
        f'{base_url}/api/v1/shipments',
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return payload, resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Create test shipments at ECmgmt')
    parser.add_argument('--url',     default='http://localhost:8000',
                        help='ECmgmt API base URL (default: http://localhost:8000)')
    parser.add_argument('--carrier', default='GLS',
                        help='Carrier code to use (default: GLS)')
    parser.add_argument('--count',   type=int, default=3,
                        help='Number of shipments to create (default: 3)')
    args = parser.parse_args()

    print(f'Creating {args.count} test shipment(s) via {args.url} using carrier {args.carrier}\n')

    created = 0
    for i in range(1, args.count + 1):
        try:
            payload, result = create_shipment(args.url, args.carrier, i)
            print(f'[{i}/{args.count}] ✓  order_id={payload["order_id"]}'
                  f'  customer={payload["customer_name"]}'
                  f'  weight={payload["weight_kg"]} kg'
                  f'\n         token={result["token"]}'
                  f'  url={result["shipment_url"]}')
            created += 1
        except requests.HTTPError as exc:
            print(f'[{i}/{args.count}] ✗  HTTP {exc.response.status_code}: {exc.response.text}',
                  file=sys.stderr)
        except Exception as exc:
            print(f'[{i}/{args.count}] ✗  {exc}', file=sys.stderr)

    print(f'\nDone: {created}/{args.count} shipment(s) created.')
    if created < args.count:
        sys.exit(1)


if __name__ == '__main__':
    main()
