'''Network manager'''
import logging
from flask import abort, jsonify, request
from neomodel import db

from app import app
from model import AtomyPerson

@app.route('/api/v1/node', defaults={'node_id': None})
@app.route('/api/v1/node/<node_id>')
def get_nodes(node_id):
    '''Gets node either by ID provided in URL or filter provided in JSON payload'''
    logger = logging.getLogger('network_manager.get_nodes()')
    if node_id is not None:
        query = 'MATCH (n {atomy_id: $atomy_id}) RETURN n'
        node = AtomyPerson.nodes.get_or_none(atomy_id=node_id)
        if node is None:
            abort(404)
        return jsonify(node)

    request_params = request.get_json()
    logger.info(request_params)
    paging = {'start': '', 'limit': 'LIMIT 100'}
    query_filter = ''
    ############# Get tree root #####################
    # if request_params is not None and request_params.get('root_id') is not None:
    #     root_id = request_params['root_id']
    # else:
    #     query = "MATCH (r) WHERE NOT EXISTS((r)-[:PARENT]->()) RETURN r.atomy_id"
    #     root_id = db.cypher_query(query)[0][0][0]
    # query_params = {'root_id': root_id}
    #################################################
    total = db.cypher_query('''
        MATCH (n:AtomyPerson)
        RETURN COUNT(n)
    ''')[0][0]
    # total = db.cypher_query('''
    #     MATCH (:AtomyPerson {atomy_id: $root_id})<-[:PARENT*0..]-(n)
    #     RETURN COUNT(n)
    # ''', params=query_params)[0][0]
    filtered = total
    if request_params is not None:
        if request_params.get('filter') is not None:
            query_filter = _get_filter(request_params['filter'])
            # query_params.update(request_params['filter'])
            query_params = request_params['filter']
            filtered = db.cypher_query(f'''
                MATCH (n:AtomyPerson)
                {query_filter}
                RETURN COUNT(n)
            ''', params=query_params)[0][0]
            # filtered = db.cypher_query(f'''
            #     MATCH (:AtomyPerson {{atomy_id: $root_id}})<-[:PARENT*0..]-(n)
            #     {query_filter}
            #     RETURN COUNT(n)
            # ''', params=query_params)[0][0]
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
        MATCH (n:AtomyPerson)
        {query_filter}
        RETURN n {paging["start"]} {paging["limit"]}
    '''
    # query = f'''
    #     MATCH (:AtomyPerson {{atomy_id: $root_id}})<-[:PARENT*0..]-(n)
    #     {query_filter}
    #     RETURN n {paging["start"]} {paging["limit"]}
    # '''
    logger.debug(query)
    result, _ = db.cypher_query(query, params=query_params)
    logger.info("Returning %s records", filtered)
    return jsonify({
        'records_total': total,
        'records_filtered': filtered,
        'data': [AtomyPerson.inflate(item[0]) for item in result]
    })

@app.route('/api/v1/node/<node_id>', methods=['patch'])
def update_node(node_id):
    node:AtomyPerson = AtomyPerson.nodes.get_or_none(atomy_id=node_id)
    if node is None:
        abort(404)
    payload = request.get_json()
    if payload is None:
        abort(400)
    if payload.get('password'): node.password = payload['password']
    if payload.get('name'): node.name = payload['name']
    node.save()
    return jsonify(node.to_dict())

@app.route('/api/v1/node/<node_id>', methods=['put'])
def save_node(node_id):
    node:AtomyPerson = AtomyPerson.nodes.get_or_none(atomy_id=node_id)
    if node is None:
        node = AtomyPerson(atomy_id=node_id).save()
    payload = request.get_json()
    if payload is None:
        abort(400)
    node.password = payload['password']
    node.name = payload['name']
    node.save()
    return jsonify(node.to_dict())



def _get_filter(filter_params):
    query_filter = []
    for k, v in filter_params.items():
        if k == '_':
            query_filter.append(f"(n.atomy_id CONTAINS ${k} OR n.name CONTAINS ${k})")
        elif k == 'id':
            if isinstance(v, str):
                query_filter.append(f'n.atomy_id CONTAINS ${k}')
            elif isinstance(v, list):
                query_filter.append(f'n.atomy_id IN ${k}')
        else:
            if v == '*':
                query_filter.append(f'n.{k} IS NOT NULL')
            else:
                query_filter.append(f'n.{k} CONTAINS ${k}')
    return 'WHERE ' + ' AND '.join(query_filter) if len(query_filter) > 0 else ''
