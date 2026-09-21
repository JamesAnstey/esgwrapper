#!/usr/bin/env python
'''
Testing generate_mapfiles.py

Load mapfiles from one dir, compare the contents of mapfiles with same filenames in another
'''

import argparse
import os

from pathlib import Path
from textwrap import dedent


PATH_SWITCH = {
    '/space/hall7/sitestore/eccc/crd/cccma/model_output/CMIP7/final': '/CCCMA_NFS/esg/esg_ng'
}
def do_path_switch(lines):
    for k,line in enumerate(lines):
        for old,new in PATH_SWITCH.items():
            if old in line and line.count(old) == 1:
                lines[k] = line.replace(old,new)

def parse_args():
    parser = argparse.ArgumentParser(
        description=dedent('''\
            Compare mapfiles in two directories.

            Comparison is done for all files present in the FIRST directory.
            An Exception is raised if any disagree.
            ''')
    )
    parser.add_argument('dir1', type=str,
                        help='first directory - only filenames in this dir will be checked')
    parser.add_argument('dir2', type=str,
                        help='second directory')

    parser.add_argument('-ps', '--path-switch', action='store_true', default=False,
                        help='use path substitution for the comparison')

    return parser.parse_args()

def main():
    args = parse_args()
    use_path_switch = args.path_switch

    path1 = Path(args.dir1)
    filenames1 = os.listdir(path1)

    path2 = Path(args.dir2)
    filenames2 = os.listdir(path2)

    for filename in filenames1:
        if not filename.endswith('.map'):
            continue
        print(f'\nChecking mapfile {filename}')

        if filename not in filenames2:
            print(f'--> File not found in {path2}, skipping')
            continue

        with open(path1 / filename) as f:
            w = f.read()
        lines = w.split('\n')

        with open(path2 / filename) as f:
            w = f.read()
        lines2 = w.split('\n')

        assert len(lines) == len(lines2)
        assert len(set(lines)) == len(set(lines2))

        if use_path_switch:
            do_path_switch(lines)
            do_path_switch(lines2)

        ok = True
        if lines != lines2:
            print('lines differ')
            lines = sorted(lines)
            lines2 = sorted(lines2)
            if lines == lines2:
                print('after sorting, lines are the same')
                ok = True
            else:
                print('lines still differ after sorting')
                ok = False
        if set(lines) != set(lines2):
            print('line contents differ')
            ok = False

        if ok:
            print('* mapfiles agree *')
        else:
            raise Exception('* mapfiles DO NOT agree *')

if __name__ == '__main__':
    main()

