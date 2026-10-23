#!/usr/bin/env python

import argparse
import json
import os

from collections import OrderedDict
from pathlib import Path
from textwrap import dedent


def parse_args():
    parser = argparse.ArgumentParser(
        description=dedent(f'''\
            Write json file with subset of records from STAC search.
            '''), formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('stac_results', type=str,
                        help='json file output from search_stac command')
    parser.add_argument('dataset_ids', type=str,
                        help='dataset ids to use: comma-separated list, or file listing datasets')

    return parser.parse_args()


def main():
    args = parse_args()

    if os.path.exists(args.dataset_ids):
        with open(args.dataset_ids) as f:
            dataset_ids = f.readlines()
    else:
        dataset_ids = args.dataset_ids.split(',')
    dataset_ids = [s.strip() for s in dataset_ids]
    dataset_ids = set([s for s in dataset_ids if len(s) > 0])
    dataset_ids = sorted(dataset_ids)

    filename = Path(args.stac_results)
    with open(filename) as f:
        d = json.load(f)
        Header = d['Header']
        datasets = d['datasets']
    datasets = OrderedDict({dataset_id: datasets[dataset_id] for dataset_id in dataset_ids})

    outfile = f'subset_{filename.stem}.json'

    out = OrderedDict({
        'Header': Header,
        'datasets': datasets
    })
    with open(outfile, 'w') as f:
        json.dump(out, f, indent=2)
        print(f'Wrote {outfile} with {len(datasets)} datasets')


if __name__ == '__main__':
    main()

