#!/usr/bin/env python
'''
Use STAC API via pystac_client to search ESGF for published CMIP7 datasets
'''

import argparse
import json
import time
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, UTC
from pystac_client import Client
# https://pystac-client.readthedocs.io/en/stable/


def parse_args():

    parser = argparse.ArgumentParser(
        description='Use STAC API to find datasets published on ESGF-NG'
        )

    esgf_index_nodes = ['east', 'west']
    parser.add_argument('index', type=str, choices=esgf_index_nodes,
                        help='ESGF-NG index node to use')

    parser.add_argument('-a', '--all', action='store_true',
                        help='return whole catalogue')

    args = parser.parse_args()
    return args

def main():

    args = parse_args()
    index = args.index

    date_str = datetime.now(UTC).strftime('%d %b %Y, %H:%M:%S UTC')
    print(f'Starting ESGF search {date_str}')
    time_taken = time.time() 

    base_query = {"collections": ["CMIP7"]}

    models = []
    models.append('CanESM5-1')
    models.append('CanESM6-0-MR')

    if args.all:
        # hack
        models = models[:1]
    else:
        print('Will search stac for these models: ' + ', '.join(models))

    datasets = []
    results = {}
    queries = []
    for model in models:
        query = deepcopy(base_query)
        query.update({
            "query": {
                "cmip7:source_id": {"eq": model},

                # "cmip7:experiment_id": {"eq": "piControl"},
                # "cmip7:variable_id": {"eq": "tas"},
                # "cmip7:frequency": {"eq": "mon"},

                # "cmip7:variant_label": {"eq": "r4i1p1f1"},

                # "cmip7:tracking_id": {"eq": "hdl:21.14107/85da197e-4aee-47a0-9a53-d0b9161b73a3"}, # nope
                # "cmip7:pid": {"eq": "hdl:21.14107/c89e9afe-754e-3594-80ea-ddd57955715c"}, # works
            }
        })
        queries.append(query)

        url_endpoint = f"https://discovery.{index}.esgf.io"
        client = Client.open(url_endpoint)

        if args.all:
            # Only specify the collection, ignore anything else
            query = deepcopy(base_query)
        
        print(f'Searching {url_endpoint} for {query}')
        search = client.search(**query)

        items = search.item_collection()
        print(f"Found {len(items)} items on ESGF-NG {index}.")

        datasets += [item.id for item in items]
        results.update({item.id: item.to_dict() for item in items})

        del items, search

        if args.all:
            break


    outfile_prefix = 'stac_found'
    # outfile_prefix = 'stac_test'
    if args.all:
        outfile_prefix = 'stac_found_all'

    # Output txt file listing dataset ids
    outfile = f'{outfile_prefix}_{index}.txt'
    w = '\n'.join(sorted(datasets, key=str.lower))
    with open(outfile, 'w') as f:
        f.write(w)
        print(f'Wrote {outfile} listing {len(datasets)} datasets found on {index}')

    time_taken = time.time() - time_taken
    fmt = '%.4f'
    print(f'ESGF search took {fmt % time_taken} s')

    # Output json file list datasets and info about them
    datasets = OrderedDict({dataset_id: results[dataset_id] for dataset_id in sorted(results.keys(), key=str.lower)})
    out = OrderedDict({
        'Header': OrderedDict({
            'index': index,
            'url_endpoint': url_endpoint,
            'search began at': date_str,
            'time taken for search (s)': time_taken,
            'queries': queries,
        }),
        'datasets': datasets
    })
    outfile = f'{outfile_prefix}_{index}.json'
    with open(outfile, 'w') as f:
        json.dump(out, f, indent=4)
        print(f'Wrote {outfile} with info on {len(datasets)} datasets found on {index}')


if __name__ == '__main__':
    main()
