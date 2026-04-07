import logging
import threading
import time
from neomodel import db, config
from tqdm import tqdm

config.DATABASE_URL = 'bolt://neo4j:1@localhost:7687'

def get_start_and_end_nodes():
    logging.info("Getting start and end nodes...")
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
threads = 0
def iterate_over_pairs(pairs):
    logging.info("Iterating through nodes...")
    global threads
    threads_lock = threading.Lock()
    def set_password(start, end):
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
        with threads_lock:
            global threads
            threads -= 1
    for start, end in tqdm(pairs):
        if threads >= 50:
            time.sleep(1)
        with threads_lock:
            threads += 1
        threading.Thread(target=set_password, args=[start, end]).start()

if __name__ == '__main__':
    nodes = get_start_and_end_nodes()
    iterate_over_pairs(nodes)