from datetime import datetime
from neomodel import db, config
from tqdm import tqdm

config.DATABASE_URL = 'bolt://neo4j:12345678@localhost:7687'
print(f"{datetime.now()}: Preparing")
empty_users, _ = db.cypher_query(
    'MATCH (a:AtomyPerson) WHERE a.username IS NULL RETURN id(a)')
empty_users = [u[0] for u in empty_users]
print(f"{datetime.now()}: Got {len(empty_users)} empty users")
# full_users, _ = db.cypher_query('''
#     MATCH (a:AtomyPerson) WHERE a.username IS NOT NULL 
#     RETURN id(a)
# ''')
# print(f"{datetime.now()}: Got {len(full_users)} complete users")
# full_users = [u[0] for u in full_users]

def do_query(user, full_users):
    global skip_list
    global threads
    global lock
    # print(f"{datetime.now()}: Sending query for {user}")
    res, _ = db.cypher_query('''
        MATCH (p:AtomyPerson) WHERE p.username IS NOT NULL
        WITH COLLECT(id(p)) AS parents
        CALL apoc.path.expandConfig($a,
            {
                minLevel: 1,
                maxLevel: 3000000,
                relationshipFilter: "PARENT>",
                labelFilter: "AtomyPerson",
                terminatorNodes: parents
            }
        ) YIELD path
        WITH nodes(path) AS nodes
        WITH nodes[..-1] AS empty_nodes, nodes[-1] AS parent
        UNWIND empty_nodes AS n
        SET n.username = parent.username, n.password = parent.password
        //RETURN id(n)
    ''', {'a': user})
    # print(f"{datetime.now()}: Got {len(res)} results")

for i in tqdm(range(0, len(empty_users), 100)):
    do_query([u for u in empty_users[i:i + 100]], [])
