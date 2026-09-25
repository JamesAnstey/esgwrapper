#!/usr/bin/env python

import argparse
import json

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
        datasets = json.load(f)['datasets']
        print('Loaded ' + filepath)


    total_size = 0
    for dataset_id, info in datasets.items():
        total_size += info['size (bytes)']

    print(f'Number of datasets: {len(datasets)}')
    # print(total_size)
    print(f'Total size: {file_size_str(total_size)}')
    






if __name__ == '__main__':
    main()
