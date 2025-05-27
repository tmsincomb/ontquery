import os 
import requests
import json
import pandas as pd
import networkx as nx


API_KEY = os.environ.get('INTERLEX_API_KEY')  # TODO: ADD YOUR API FROM SCICRUNCH HERE


# Pull Anchor tree
def get_relationships_df():
    query = {
        "query": {
            "bool" : {
                "must" : {
                    "term" : { "type" : "termset" }
                }
            }
        }
    }
    params = {
        'size': 10000,  # 10K is max for ES query unless you use a scoller.
        'from': 0,
        'key': API_KEY,
        'query': json.dumps(query.get('query', query)),
    }
    response = requests.get('https://scicrunch.org/api/1/term/elastic/search', params=params)
    json_list = [
        {**data['_source'], **{'ilx': data['_id']}}  # ilx itself is in upper meta and needs to be merged
        for data in response.json()['data']['hits']['hits']  # ES general _search has tedious nested hits
    ]
    # Get PNS tree
    relationships_df = pd.json_normalize(json_list, record_path=['relationships'])
    relationships_df = relationships_df.drop_duplicates()
    return relationships_df

def get_nodes(df, root='ilx_0775451'):
    G = nx.from_pandas_edgelist(df, 'term1_ilx', 'term2_ilx')
    edges = nx.bfs_edges(G, root) 
    nodes = [root] + [v for u, v in edges]
    return nodes

def get_entities(nodes):
    # Populate PNS tree; term to large to call at once
    json_list = []
    batch_size = 300  # max 300 for server to allow
    for i in range(0, len(nodes), batch_size):
        query = {
            "query": {
                "ids" : {
                    "values" : nodes[i:i+batch_size]
                }
            }
        }
        params = {
            'size': 10000,  # 10K is max for ES query unless you use a scoller.
            'from': 0,
            'key': API_KEY,
            'query': json.dumps(query.get('query', query)),
        }
        response = requests.get('https://scicrunch.org/api/1/term/elastic/search', params=params)
        json_list += [
            {**data['_source'], **{'ilx': data['_id']}}  # ilx itself is in upper meta and needs to be merged
            for data in response.json()['data']['hits']['hits']  # ES general _search has tedious nested hits
        ]
    df = pd.DataFrame(json_list)  # allows a CSV type output from the nested records
    return df


if __name__ == '__main__':
    relationships_df = get_relationships_df()
    nodes = get_nodes(relationships_df, root='ilx_0775451')  # PNS as root
    df = get_entities(nodes)
    # df.head()
    df.to_csv('TermSets-PNS.csv', index=False)