#!/usr/bin/env python
'''
Using an inventory json file as input, e.g. one produced by running
    publish -i
get info about the files according to the input options set.
Nothing is done by default, the user has to specify each kind of info to get
using the input flags. For example, this:
    ./get_file_stats.py inventory.json -c
computes the chksum for every file of every dataset listed in inventory.json.
'''

import argparse
import hashlib
import json
import os

from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CHKSUM_TYPE = 'sha256'
DEFAULT_OUTFILE = 'file_stats.json'

def parse_args():
    parser = argparse.ArgumentParser(
        description='Get info about files in datasets'
    )

    parser.add_argument('input', type=str,
                        help='json inventory file')

    parser.add_argument('-o', '--outfile', type=str, default=DEFAULT_OUTFILE,
                        help=f'output file (json), default: {DEFAULT_OUTFILE}')

    parser.add_argument('-c', '--chksum', action='store_true', default=False,
                        help='compute file chksum')
    parser.add_argument('-ct', '--chksum-type', type=str, default=DEFAULT_CHKSUM_TYPE,
                        help=f'type of chksum to compute, default: {DEFAULT_CHKSUM_TYPE}')

    parser.add_argument('-s', '--size', action='store_true', default=False,
                        help='get file size')
    parser.add_argument('-a', '--access-time', action='store_true', default=False,
                        help='get time of most recent access')
    parser.add_argument('-m', '--mod-time', action='store_true', default=False,
                        help='get time of most recent content modification')

    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    chksum_type = args.chksum_type
    convert_to_datetime = True

    with open(args.input) as f:
        inventory = json.load(f)

    dataset_ids = sorted(inventory['datasets'].keys())
    file_stats = OrderedDict()
    for dataset_id in dataset_ids:
        info = inventory['datasets'][dataset_id]
        file_stats[dataset_id] = OrderedDict({
            'path': info['path'],
            'files': OrderedDict()
        })
        for filename in info['filenames']:
            filepath = Path(info['path']) / filename
            file_stat = OrderedDict()
            file_stats[dataset_id]['files'][filename] = file_stat

            if args.chksum:
                with open(filepath, 'rb') as f:
                    file_stat['chksum'] = hashlib.file_digest(f, chksum_type).hexdigest()

            stat = os.stat(filepath)
            if args.size:
                file_stat['size'] = stat.st_size
            if args.mod_time:
                file_stat['mod time'] = stat.st_mtime
            if args.access_time:
                file_stat['access time'] = stat.st_atime
                # Note, if chksum is computed then in general the last access time will be changed

            if convert_to_datetime:
                for s in ['mod time', 'access time']:
                    if s not in file_stat:
                        continue
                    dt = datetime.fromtimestamp(file_stat[s], timezone.utc)
                    file_stat[s] = dt.strftime('%Y-%m-%d %H:%M:%S UTC')

    n = len(file_stats)
    out = OrderedDict({
        'Header': OrderedDict({
            'chksum type': chksum_type,
            'no. of datsaets': n
        }),
        'datasets': file_stats
    })
    outfile = args.outfile
    with open(outfile, 'w') as f:
        json.dump(out, f, indent=4)
        print(f'Wrote {outfile} with file stats for {n} datasets')
    