#!/usr/bin/env python
'''
Generate mapfiles for use with esgpublish (from esgcet package).
'''

import argparse
import hashlib
import json
import logging
import os
import sys
import time

from collections import OrderedDict
from pathlib import Path

from esgfsearch import file_size_str

logger = logging.getLogger('generate_mapfiles')
# logging.basicConfig(filename='mapfile_generation.log', filemode='w', level=logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler('mapfile_generation.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)

chksum_type = 'sha256'

PATH_SWITCH = {
    '/space/hall7/sitestore/eccc/crd/cccma/model_output/CMIP7/final': '/CCCMA_NFS/esg/esg_ng'
}

def parse_args():
    parser = argparse.ArgumentParser(
        description='Create mapfiles for use by esgpublish'
    )

    parser.add_argument('input', type=str,
                        help='json inventory file')
    parser.add_argument('outdir', type=str,
                        help='output directory to store mapfiles (will be created if needed)')

    parser.add_argument('-n', '--number', type=int,
                        help='number of datasets to use from list of datasets (default: all)')
    parser.add_argument('--clobber', action='store_true', default=False,
                        help='overwrite mapfile if it already exists')
    parser.add_argument('--orig-path', action='store_true', default=False,
                        help='leave the original path unaltered (ignore any path aliases)')
    parser.add_argument('-id', '--dataset-ids', type=str,
                        help='dataset ids to use: comma-separated list, or file listing datasets')

    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()

    path_switch = not args.orig_path

    # Example contents of a CMIP7 mapfile (there's one line like this for each file in a dataset):
    # MIP-DRS7.CMIP7.CMIP.CCCma.CanESM5-1.1pctCO2.r1i1p2f1.glb.mon.pr.tavg-u-hxy-u.g120.v20190429 | /space/hall7/sitestore/eccc/crd/cccma/model_output/CMIP7/final/MIP-DRS7/CMIP7/CMIP/CCCma/CanESM5-1/1pctCO2/r1i1p2f1/glb/mon/pr/tavg-u-hxy-u/g120/v20190429/pr_tavg-u-hxy-u_mon_glb_g120_CanESM5-1_1pctCO2_r1i1p2f1_185001-190012.nc | 16055367 | mod_time=1787125699.7238321 | checksum=47e91c66d8ee78a26ef10b103bc9b981a628d855fb92380d89a91ac9e694f8d0 | checksum_type=SHA256
    contents_template = '{dataset_id} | {filepath} | {size} | mod_time={mod_time} | checksum={chksum} | checksum_type={chksum_type}'

    mapfile_dir = args.outdir
    if not os.path.exists(mapfile_dir):
        os.makedirs(mapfile_dir)
    mapfile_dir = Path(mapfile_dir)

    with open(args.input) as f:
        d = json.load(f)
        datasets = d['datasets']

    dataset_ids = sorted(datasets.keys(), key=str.lower)

    if args.dataset_ids:
        if os.path.exists(args.dataset_ids):
            with open(args.dataset_ids) as f:
                dataset_ids = f.readlines()
        else:
            dataset_ids = args.dataset_ids.split(',')
        dataset_ids = [s.strip() for s in dataset_ids]

    if args.number:
        dataset_ids = dataset_ids[:args.number]

    datasets = OrderedDict({s : datasets[s] for s in dataset_ids})
    del dataset_ids

    n, k = len(datasets), 0
    time_taken = {}
    for dataset_id, info in datasets.items():

        # Example mapfile filename for CMIP7:
        #   MIP-DRS7.CMIP7.ScenarioMIP.CCCma.CanESM5-1.esm-scen7-h.r18i1p2f1.glb.mon.wmo.tavg-ol-hxy-sea.g127.v20190429.map
        outfile = mapfile_dir / f'{dataset_id}.map'
        if not args.clobber and os.path.exists(outfile):
            logger.info(f' Not overwriting existing mapfile: {outfile}')
            continue

        path, filenames = info['path'], info['filenames']
        contents = OrderedDict()
        k += 1
        logger.info(f' Generating mapfile for dataset ({k} of {n}): {dataset_id} ({info["size (human readable)"]})')
        logger.info(f' Dataset path: {path}')
        start_time = time.time()
        for filename in filenames:
            file_stat = {
                'dataset_id': dataset_id,
                'filepath': os.path.join(path, filename)
            }
            filepath = Path(path) / filename
            stat = os.stat(filepath)
            file_stat['size'] = stat.st_size
            file_stat['mod_time'] = stat.st_mtime
            logger.info(f' {filename} ({file_size_str(file_stat["size"])})')
            with open(filepath, 'rb') as f:
                file_stat.update({
                    'chksum': hashlib.file_digest(f, chksum_type).hexdigest(),
                    'chksum_type': chksum_type.upper(),
                })
            contents[filename] = file_stat

        if path_switch:
            for filename, file_stat in contents.items():
                for orig_path, new_path in PATH_SWITCH.items():
                    if file_stat['filepath'].startswith(orig_path):
                        rel_path = file_stat['filepath'].partition(orig_path)[-1].strip(os.path.sep)
                        file_stat['filepath'] = os.path.normpath(os.path.join(new_path, rel_path))

        lines = []
        for filename in filenames:
            lines.append(contents_template.format(**contents[filename]))

        with open(outfile, 'w') as f:
            f.write('\n'.join(lines) + '\n')

        time_taken[dataset_id] = time.time() - start_time
        logger.info(f' Time (s) for {dataset_id}: {time_taken[dataset_id]}')
        logger.info(f' Wrote {outfile}')

    total_time = sum(time_taken.values())
    total_size = sum([info['size (bytes)'] for info in datasets.values()])
    size_str = file_size_str(total_size)
    fmt = '%.2f'
    # logger.info(' SUMMARY:')
    logger.info(f'\n  Total time for mapfile generation: {fmt % total_time} s '
                f'({fmt % (total_time/60)} min, {fmt % (total_time/3600)} hr)'
                f'\n  Total no. of datasets: {len(datasets)}'
                f'\n  Total size of datasets: {size_str}'
                )
