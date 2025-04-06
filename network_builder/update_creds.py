import itertools
from neomodel import db, config
from tqdm import tqdm

config.DATABASE_URL = 'bolt://neo4j:1@localhost:7687'

def get_start_and_end_nodes():
    print("Getting start and end nodes...")
    # (a:AtomyPerson{atomy_id:'26298372'})<-[:PARENT*0..]-
    res, _ = db.cypher_query('''
        MATCH (start:AtomyPerson)<-[:PARENT*]-(end:AtomyPerson) 
        WHERE 
            start.password <> 'mkk03020529!!' 
            AND (
                end.password <> 'mkk03020529!!' 
                OR (
                    end.password = 'mkk03020529!!' 
                    AND NOT EXISTS ((end)<-[:PARENT]-(:AtomyPerson))
                )
            ) 
        RETURN start.atomy_id, end.atomy_id 
    ''')
    return res

def iterate_over_pairs(pairs):
    print("Iterating through nodes...")
    for start, end in tqdm(pairs):
        res, _ = db.cypher_query('''
            MATCH path = (start:AtomyPerson{atomy_id:$start})<-[:PARENT*]-(end:AtomyPerson{atomy_id:$end})
            WITH start, nodes(path) as chain_nodes
            WHERE 
                ALL(n IN chain_nodes[1..-1] WHERE n.password = 'mkk03020529!!')
                AND (
                    size(chain_nodes) > 2
                    OR chain_nodes[-1].password = 'mkk03020529!!'
                )

            UNWIND chain_nodes[1..] AS n
            WITH DISTINCT start, n WHERE n.password = 'mkk03020529!!'
            SET n.username = start.username, n.password = start.password
        ''', {'start': start, 'end': end})


if __name__ == '__main__':
    nodes = get_start_and_end_nodes()
    iterate_over_pairs(nodes)