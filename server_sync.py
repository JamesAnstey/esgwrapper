#!/usr/bin/env python

import argparse
import os


parser = argparse.ArgumentParser(
    description='sync repo to/from CRD ESGF server (invoke on science HPC)'
    )
parser.add_argument('action', choices=['send', 'get'])
parser.add_argument('files', nargs='+', type=str, help='files to transfer (whitespace-separated list)')
args = parser.parse_args()

server = 'eccc-esgf.collab.science.gc.ca'
user = 'acrnpub'
repo = 'esgwrapper'
path = os.path.normpath(f'/esg/publish/{repo}')

if not os.path.basename(os.getcwd()) == repo:
    raise OSError('Invoke this in top level of repository: ' + repo)

cmds = []
if args.action == 'send':
    cmds.append(f'rsync -ua {" ".join(args.files)} {user}@{server}:{path}')
elif args.action == 'get':
    for filename in args.files:
        cmds.append(f'rsync -ua {user}@{server}:{path}/{filename} .')

for cmd in cmds:
    print(cmd)
    os.system(cmd)

