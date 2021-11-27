from calendar import monthrange
from datetime import datetime
import json
import requests
from model import AtomyPerson
from utils.atomy import SessionManager


def get_pvs():
    nodes = get_nodes_creds()
    for username, password in nodes.items():
        session = SessionManager(username, password)
        data = get_node_stats(session)

def get_node_stats(session):
    today = datetime.today()
    month_range = monthrange(today.year, today.month)
    start_date = today.strftime('%Y-%m-01' if today.day < 16 else '%Y-%m-16')
    end_date = today.strftime(f'%Y-%m-{15 if today.day < 16 else month_range[1]:02d}')
    data = session.get_json(url=CONFIG['STATS_URL'],
        headers={"Content-type": "application/json"},
        raw_data=json.dumps({
            'StartDt': start_date,
            'EndDt': end_date,
            'CurrentPageNo': 1,
            'PageSize': "30"
        })
    )
    return data

def get_nodes_creds():
    nodes_creds = {}
    for resource in CONFIG['ORDER_MASTER_NODES']:
        response = requests.get(resource['url'], headers={
            'Content-type': 'application/json',
            'Authentication-token': resource['token']
        })
        data = response.json()
        nodes_creds.update({node['username']: node['password'] for node in data})
    return nodes_creds

CONFIG = json.load(open("network_builder/config.json"))

get_pvs()
