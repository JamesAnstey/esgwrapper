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
from datetime import datetime, UTC
from pathlib import Path

from esgwrapper.utils.esgfsearch import file_size_str

PATH_SWITCH = {
    '/space/hall7/sitestore/eccc/crd/cccma/model_output/CMIP7/final': '/CCCMA_NFS/esg/esg_ng'
}

DEFAULT_CHKSUM_TYPE = 'sha256'

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
    parser.add_argument('--chksum-type', type=str, default=DEFAULT_CHKSUM_TYPE,
                        help='type of chksum to compute, default: %(default)s')

    return parser.parse_args()

def main():
    args = parse_args()
    path_switch = not args.orig_path
    chksum_type = args.chksum_type

    logger = logging.getLogger('generate_mapfiles')
    date_run = datetime.now(UTC)
    date_run_str = date_run.strftime('%Y.%m.%d_%H.%M.%S_UTC')
    log_dir = Path('logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logfile = log_dir / f'mapfiles_{date_run_str}.log'
    handlers=[
        logging.FileHandler(logfile, mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
    logging.basicConfig(
        level=logging.INFO,
        handlers=handlers
    )


    # Example contents of a CMIP7 mapfile (there's one line like this for each file in a dataset):
    # MIP-DRS7.CMIP7.CMIP.CCCma.CanESM5-1.1pctCO2.r1i1p2f1.glb.mon.pr.tavg-u-hxy-u.g120.v20190429 | /space/hall7/sitestore/eccc/crd/cccma/model_output/CMIP7/final/MIP-DRS7/CMIP7/CMIP/CCCma/CanESM5-1/1pctCO2/r1i1p2f1/glb/mon/pr/tavg-u-hxy-u/g120/v20190429/pr_tavg-u-hxy-u_mon_glb_g120_CanESM5-1_1pctCO2_r1i1p2f1_185001-190012.nc | 16055367 | mod_time=1787125699.7238321 | checksum=47e91c66d8ee78a26ef10b103bc9b981a628d855fb92380d89a91ac9e694f8d0 | checksum_type=SHA256
    contents_template = '{dataset_id} | {filepath} | {size} | mod_time={mod_time} | checksum={chksum} | checksum_type={chksum_type}'

    # mapfile_dir: top-level output path for storing mapfiles
    # mapfile_subdir_template (if given): how to construct subdirs for mapfiles
    mapfile_dir = args.outdir
    mapfile_dir = Path(mapfile_dir)
    # TODO: avoid hard-coding this for cmip7, get from config-publisher.yaml instead
    # mapfile_subdir_template = '{drs_specs}/{mip_era}/{activity_id}/{institution_id}/{source_id}/{experiment_id}/{variant_label}'
    mapfile_subdir_template = ''

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
        k += 1
        path, filenames = info['path'], info['filenames']
        logger.info(f' Generating mapfile for dataset ({k} of {n}): {dataset_id} ({info["size (human readable)"]})')
        logger.info(f' Dataset path: {path}')

        # Example mapfile filename for CMIP7:
        #   MIP-DRS7.CMIP7.ScenarioMIP.CCCma.CanESM5-1.esm-scen7-h.r18i1p2f1.glb.mon.wmo.tavg-ol-hxy-sea.g127.v20190429.map

        mapfile_subdir = mapfile_subdir_template.format(**info['params'])
        outpath = mapfile_dir / mapfile_subdir
        if not os.path.exists(outpath):
            os.makedirs(outpath)
        outfile = outpath / f'{dataset_id}.map'
        if not args.clobber and os.path.exists(outfile):
            logger.info(f' Not overwriting existing mapfile: {outfile}')
            continue

        contents = OrderedDict()
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

    print(f'\nWrote logfile: {logfile}')

if __name__ == '__main__':
    main()
