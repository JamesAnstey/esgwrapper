#!/usr/bin/env python

import argparse
import json
import os

from esgwrapper.utils.esgfsearch import file_size_str



def parse_args():

    parser = argparse.ArgumentParser(
        description='Publish CCCma datasets to ESGF'
        )

    parser.add_argument('inventory', type=str,
                        help='json file listing datasets, as produced by "publish -i" or "publish -d"')

    return parser.parse_args()

def main():
    args = parse_args()

    # Load inventory
    filepath = args.inventory
    with open(filepath, 'r') as f:
        d = json.load(f)
        datasets = d['datasets']
        header = d['Header']
        print('Loaded ' + os.path.abspath(filepath))


    total_size = 0
    for dataset_id, info in datasets.items():
        total_size += info['size (bytes)']

    n = len(datasets)
    assert n == header['no. of datasets found']
    print('Inventory finished at: ' + header['date of inventory'])
    print('Base paths searched:')
    for path in header['base paths searched']:
        print(f'  {path}')
    print('Dataset paths searched:')
    for path in header['dataset paths searched']:
        print(f'  {path}')
    print(f'Number of datasets found: {len(datasets)}')
    print(f'Total size: {file_size_str(total_size)}')
 



if __name__ == '__main__':
    main()
