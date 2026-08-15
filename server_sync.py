#!/usr/bin/env python

import argparse
import os

# Set default path on server to copy to
# For server eccc-esgf.collab.science.gc.ca (2025 & earlier):
# repo = 'esgwrapper'
# For server
# path = os.path.normpath(f'/esg/publish/{repo}')
# 
path = '/datalocal/home/scrd106/esgf_publishing/cmip7_dev'

parser = argparse.ArgumentParser(
    description='sync repo to/from CRD ESGF server (invoke on science HPC)',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
parser.add_argument('project', type=str,
                    help=f'ESGF project to publish to, e.g. "cmip7" (case-insensitive)')
parser.add_argument('action', choices=['send', 'get'])
parser.add_argument('files', nargs='+', type=str, help='files to transfer (whitespace-separated list)')

parser.add_argument('--path', type=str, default='/datalocal/home/{user}/esgf_publishing/{project}',
                    help=f'path on server to copy to')
parser.add_argument('--server', type=str, default='eccc-esgf2.collab.science.gc.ca',
                    help=f'server hostname, default:')
parser.add_argument('--user', type=str,
                    help=f'user account on the server used for the project, e.g. "scrd106"')


args = parser.parse_args()
valid_projects = [
    'cmip7',
    'cmip6',
    'cordex-cmip6',
    'cmip6plus'
]
project = args.project.lower()
if project not in valid_projects:
    raise ValueError(f'Unknown ESGF project: {project}, update valid_projects if needed')
user = args.user
if not user:
    # Specify user based on the project
    project_user = {
        'cmip7': 'scrd106',
        'cordex-cmip6': 'scrd117',
    }
    if user not in project_user:
        raise ValueError(f'Need to specify server account used for project {project}')
    user = project_user[project]

path = args.path.format(user=user, project=project)
# server = 'eccc-esgf.collab.science.gc.ca'
# server = 'eccc-esgf2.collab.science.gc.ca'
# user = 'acrnpub'

path = os.path.normpath(path)
breakpoint()


# if not os.path.basename(os.getcwd()) == repo:
#     raise OSError('Invoke this in top level of repository: ' + repo)

cmds = []
if args.action == 'send':
    cmds.append(f'rsync -ua {" ".join(args.files)} {user}@{server}:{path}')
elif args.action == 'get':
    for filename in args.files:
        cmds.append(f'rsync -ua {user}@{server}:{path}/{filename} .')

for cmd in cmds:
    print(cmd)
    os.system(cmd)

