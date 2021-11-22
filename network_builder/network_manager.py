'''Network manager'''
import logging
from flask import jsonify, request
from neomodel import db

from app import app
from model import AtomyPerson

@app.route('/api/v1/node', defaults={'node_id': None})
@app.route('/api/v1/node/<node_id>')
def get_nodes(node_id):
    '''Gets node either by ID provided in URL or filter provided in JSON payload'''
    logger = logging.getLogger('network_manager.get_nodes()')
    logger.info(request.get_json())
    if node_id is not None:
        query = 'MATCH (n {atomy_id: $atomy_id}) RETURN n'
        result, _ = db.cypher_query(query)
        if len(result) > 0:
            return jsonify(result[0][0])
    else:
        params = request.get_json()
        root_id = None
        paging = {'start': '', 'limit': 'LIMIT 100'}
        query_filter = ''
        if params is not None:
            if params.get('filter') is not None:
                query_filter = _get_filter(params['filter'])
            if params.get('start') is not None and params.get('limit') is not None:
                paging['start'] = 'SKIP ' + str(params['start'])
                paging['limit'] = 'LIMIT ' + str(params['limit'])
            elif params.get('paging') is not None:
                try:
                    paging['start'] = 'SKIP ' + str((int(params['paging']['page']) - 1) *
                                                    int(params['paging']['page_size']))
                    paging['limit'] = 'LIMIT ' + str(params['paging']['page_size'])
                except:
                    pass
            root_id = params.get('root_id')
        if root_id is None:
            query = "MATCH (r) WHERE NOT EXISTS((r)-[:PARENT]->()) RETURN r.atomy_id"
            root_id = db.cypher_query(query)[0][0][0]

        total = db.cypher_query('''
            MATCH (:AtomyPerson {atomy_id: $root_id})<-[:PARENT*0..]-(n)
            RETURN COUNT(n)
        ''', params={'root_id': root_id})[0][0]
        filtered = db.cypher_query(f'''
            MATCH (:AtomyPerson {{atomy_id: $root_id}})<-[:PARENT*0..]-(n)
            {query_filter}
            RETURN COUNT(n)
        ''', params={'root_id': root_id, **params['filter']})[0][0]

        query = f'''
            MATCH (:AtomyPerson {{atomy_id: $root_id}})<-[:PARENT*0..]-(n)
            {query_filter}
            RETURN n {paging["start"]} {paging["limit"]}
        '''
        logger.debug(query)
        result, _ = db.cypher_query(query,
                                    params={'root_id': root_id, **params['filter']})
        logger.info("Returning %s records", filtered)
        return jsonify({
            'records_total': total,
            'records_filtered': filtered,
            'data': [AtomyPerson.inflate(item) for item in result]
        })

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
