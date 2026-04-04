'''Network manager'''
from datetime import date, timedelta
import json
import logging
from multiprocessing.pool import ThreadPool
from os import environ
from random import random
from time import sleep

import re

import docker
import docker.errors
from flask import Response, abort, jsonify, request
from neomodel import db
from werkzeug.exceptions import BadRequest

from netman_app import app
from common.model import AtomyPerson

BUILDER_CONTAINER_NAME = 'network-builder'
BUILDER_IMAGE = environ.get('BUILDER_IMAGE', 'ralfeus/network-builder:stable')
BUILDER_NETWORK = environ.get('BUILDER_NETWORK', 'order')

logging.getLogger('neo4j').setLevel(logging.INFO)


def _get_builder_container():
    """Returns the running builder container, or None if not running."""
    try:
        client = docker.from_env()
        container = client.containers.get(BUILDER_CONTAINER_NAME)
        if container.status == 'running':
            return container
    except (docker.errors.NotFound, docker.errors.DockerException):
        pass
    return None


def _test_db_connection():
    try:
        db.cypher_query("MATCH () RETURN 1 LIMIT 1")
        return True
    except Exception:
        return False


@app.before_request
def test_db_connection():
    if not _test_db_connection():
        response = jsonify(status="error", description="Neo4j isn't available")
        response.status_code = 500
        return response


@app.route('/api/v1/builder/status')
def get_builder_status():
    container = _get_builder_container()
    if container is not None:
        response = {'status': 'running'}
        logs = container.logs(tail=100).decode('utf-8', errors='replace')
        for line in reversed(logs.splitlines()):
            nodes_match = re.search(r'Progress on:(\d+) nodes updated', line)
            elapsed_match = re.search(r'elapsed:([^\s]+)', line)
            if nodes_match and elapsed_match:
                response['progress'] = f"elapsed:{elapsed_match.group(1)}; {nodes_match.group(1)} nodes updated"
                break
        return jsonify(response)
    else:
        return jsonify({'status': 'not running'})


@app.route('/api/v1/builder/start')
def start_builder():
    logging.info("Wait for another request to start building")
    sleep(random() * 5)
    if _get_builder_container() is not None:
        return jsonify({'status': 'already running'})

    days = int(request.args.get('days') or 0)
    threads = request.args.get('threads') or '60'
    last_updated = date.today() - timedelta(days=days)
    try:
        client = docker.from_env()

        # Remove stale container from a previous run if present
        try:
            old = client.containers.get(BUILDER_CONTAINER_NAME)
            old.remove(force=True)
        except docker.errors.NotFound:
            pass

        root = request.args.get('root') or 'S5832131'
        client.containers.run(
            BUILDER_IMAGE,
            command=[
                '--user', 'S5832131',
                '--password', 'mkk03020529!!',
                '--root', root,
                '--max-threads', threads,
                '--nodes', request.args.get('nodes') or '0',
                '--last-updated', last_updated.strftime('%Y-%m-%d'),
                '--socks5_proxy', environ.get('SOCKS5_PROXY') or '',
                '--repeat',
            ],
            name=BUILDER_CONTAINER_NAME,
            environment={
                'NEO4J_URL': environ.get('NEO4J_URL', ''),
                'SOCKS5_PROXY': environ.get('SOCKS5_PROXY', ''),
            },
            network=BUILDER_NETWORK,
            extra_hosts={'host.docker.internal': 'host-gateway'},
            detach=True,
            auto_remove=True,
        )
        logging.info("Started builder container %s", BUILDER_CONTAINER_NAME)
        return jsonify({'status': 'started'})
    except docker.errors.DockerException as e:
        if isinstance(e.__cause__, (FileNotFoundError, ConnectionError)):
            logging.error("Docker is not available: %s", e)
            return jsonify({'status': 'error', 'description': 'Docker is not available'}), 503
        logging.exception(e)
        return jsonify({'status': "couldn't start"})
    except Exception as e:
        logging.exception(e)
        return jsonify({'status': "couldn't start"})


@app.route('/api/v1/builder/stop')
def stop_builder():
    container = _get_builder_container()
    if container is not None:
        container.stop()
        return jsonify({'status': 'stopped'})
    return jsonify({'status': "didn't stop - not running"})


@app.route('/api/v1/node', defaults={'node_id': None})
@app.route('/api/v1/node/<node_id>')
def get_nodes(node_id):
    '''Gets node either by ID provided in URL or filter provided in JSON payload'''
    def get_total(query_params):
        quantity, _ = db.cypher_query('''
            MATCH (q:Quantity{root: $root_id, filter: ""}) RETURN q.total
        ''', params=query_params)
        if len(quantity) == 0:
            quantity = db.cypher_query('''
                MATCH (:AtomyPerson {atomy_id: $root_id})<-[:PARENT*0..]-(n:AtomyPerson)
                WITH COUNT(n) AS total
                MERGE (q:Quantity{root: $root_id, filter: "", total: total})
                RETURN total
            ''', params=query_params)
        return quantity
    def get_filtered(query_filter, query_params):
        quantity, _ = db.cypher_query('''
            MATCH (q:Quantity{root: $root_id, filter: $params}) RETURN q.total
        ''', params={**query_params, 'params': json.dumps(query_params)})
        if len(quantity) == 0:
            quantity = db.cypher_query(f'''
                MATCH (:AtomyPerson {{atomy_id: $root_id}})<-[:PARENT*0..]-(n:AtomyPerson)
                {query_filter}
                WITH COUNT(n) AS total
                MERGE (q:Quantity{{root: $root_id, filter: $params, total: total}})
                RETURN total
            ''', params={**query_params, 'params': json.dumps(query_params)})
        return quantity
    logger = logging.getLogger('network_manager.get_nodes()')
    body = None
    try:
        body = request.get_json()
    except BadRequest:
        pass # No JSON body is mandatory
    logger.debug("Request body: %s", body)
    if node_id is not None:
        query = '''
            MATCH (n:AtomyPerson {atomy_id: $atomy_id})
            OPTIONAL MATCH (c:Center {name: n.center})
            RETURN n, c.code
        '''
        result = db.cypher_query(query, params={'atomy_id': node_id})
        if len(result[0]) == 0:
            abort(Response(
                json.dumps({'description': f"Node with ID {node_id} not found", 'status': 404}),
                status=404, content_type='application/json'))
        node = AtomyPerson.inflate(result[0][0][0], lazy=False)
        response = node.to_dict()
        response['center_code'] = result[0][0][1]
        return jsonify(response)

    request_params = body
    paging = {'start': '', 'limit': 'LIMIT 100'}
    query_filter = ''
    ############# Get tree root #####################
    if request_params is not None and request_params.get('root_id') is not None:
        root_id = request_params['root_id']
    else:
        logger.info("Getting root ID")
        query = "MATCH (r) WHERE NOT EXISTS((r)-[:PARENT]->()) RETURN r.atomy_id"
        root_id = db.cypher_query(query)[0][0][0]
    query_params = {'root_id': root_id, 'test': 'test'}
    #################################################
    logger.info("Getting total number of nodes")
    total_thread = ThreadPool().apply_async(get_total, args=(query_params,))
    filtered_thread = total_thread
    if request_params is not None:
        if request_params.get('filter') is not None:
            query_filter = _get_filter(request_params['filter'])
            query_params = {**query_params, **request_params['filter']}
            logger.info("Getting number of filtered nodes")
            filtered_thread = ThreadPool().apply_async(get_filtered, args=(query_filter, query_params))
        if request_params.get('start') is not None and request_params.get('limit') is not None:
            paging['start'] = 'SKIP ' + str(request_params['start'])
            paging['limit'] = 'LIMIT ' + str(request_params['limit'])
        elif request_params.get('paging') is not None:
            try:
                paging['start'] = 'SKIP ' + str((int(request_params['paging']['page']) - 1) *
                                                int(request_params['paging']['page_size']))
                paging['limit'] = 'LIMIT ' + str(request_params['paging']['page_size'])
            except:
                pass

    query = f'''
        MATCH (:AtomyPerson {{atomy_id: $root_id}})<-[:PARENT*0..]-(n:AtomyPerson)
        {query_filter}
        RETURN n {paging["start"]} {paging["limit"]}
    '''
    logger.debug(query)
    result, _ = db.cypher_query(query, params=query_params)
    logger.info("Got %s records", len(result))
    total = total_thread.get()[0][0]
    filtered = filtered_thread.get()[0][0]
    logger.info("Returning %s records", filtered)
    return jsonify({
        'records_total': total,
        'records_filtered': filtered,
        'data': [AtomyPerson.inflate(item[0]) for item in result]
    })


@app.route('/api/v1/node/<node_id>', methods=['patch'])
def update_node(node_id):
    node: AtomyPerson = AtomyPerson.nodes.get_or_none(atomy_id=node_id)
    if node is None:
        abort(404)
    payload = request.get_json()
    if payload is None:
        abort(400)
    if payload.get('id') is not None:
        if node.parent_id is not None:
            abort(Response("Can't update ID of the node imported from Atomy", status=409))
        if AtomyPerson.nodes.get_or_none(atomy_id=payload['id']) is not None:
            abort(Response(f"The node is ID {payload['id']} already exists", status=409))
        node.atomy_id = payload['id']
    if payload.get('password'): node.password = payload['password']
    if payload.get('name'): node.name = payload['name']
    node.save()
    return jsonify(node.to_dict())


@app.route('/api/v1/node/<node_id>', methods=['put'])
def save_node(node_id):
    try:
        payload = request.get_json()
        if payload is None:
            raise BadRequest()
    except BadRequest:
        abort(400, jsonify(description="No JSON body"))
    node:AtomyPerson = AtomyPerson.nodes.get_or_none(atomy_id=node_id)
    if node is None:
        node = AtomyPerson(atomy_id=node_id).save()
    node.password = payload['password']
    node.name = payload['name']
    node.save()
    return jsonify(node.to_dict())


@app.route('/api/v1/node/<node_id>/update', methods=['post'])
def update_node_from_atomy(node_id):
    container_name = f'network-builder-{node_id}'
    try:
        client = docker.from_env()
        try:
            old = client.containers.get(container_name)
            if old.status == 'running':
                return {'status': 'already running'}, 200
            old.remove(force=True)
        except docker.errors.NotFound:
            pass
        client.containers.run(
            BUILDER_IMAGE,
            command=[
                '--user', 'S5832131',
                '--password', 'mkk03020529!!',
                '--max-threads', '50',
                '--root', node_id,
            ],
            name=container_name,
            environment={
                'NEO4J_URL': environ.get('NEO4J_URL', ''),
                'SOCKS5_PROXY': environ.get('SOCKS5_PROXY', ''),
            },
            network=BUILDER_NETWORK,
            extra_hosts={'host.docker.internal': 'host-gateway'},
            detach=True,
        )
        return {'status': 'success'}, 200
    except Exception as e:
        logging.exception(e)
        return {'status': 'error'}, 500


@app.route('/api/v1/node/<node_id>/update')
def get_node_fetch_status(node_id):
    container_name = f'network-builder-{node_id}'
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        if container.status == 'running':
            return {'status': 'running'}, 200
        container.remove()
        return {'status': 'finished'}, 200
    except docker.errors.NotFound:
        return {'status': 'not running'}, 200
    except Exception:
        return {'status': 'not running'}, 200


def _get_filter(filter_params):
    query_filter = []
    for k, v in filter_params.items():
        if k == 'id':
            if isinstance(v, str):
                query_filter.append(f'n.atomy_id CONTAINS ${k}')
            elif isinstance(v, list):
                query_filter.append(f'n.atomy_id IN ${k}')
        else:
            query_filter.append(f'n.{k} CONTAINS ${k}')
    return 'WHERE ' + ' AND '.join(query_filter) if len(query_filter) > 0 else ''
