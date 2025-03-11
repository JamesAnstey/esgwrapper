#!/usr/bin/env python
'''
Thin wrapper around ESGF publishing software.

https://esg-publisher.readthedocs.io/en/main/index.html

'''


import argparse
import datetime
import json
import os
import yaml
from collections import OrderedDict

from tools import find_datasets, match_params


parser = argparse.ArgumentParser(
    description='Publish CCCma datasets to ESGF'
    )
parser.add_argument('-c', '--config', type=str, default='config-datasets.yaml',
                    help='name of config file containing datasets to publish, default: %(default)s')
parser.add_argument('-m', '--mapfile', action='store_true', default=False,
                    help='generate mapfiles')
parser.add_argument('-p', '--publish', action='store_true', default=False,
                    help='publish to ESGF')
parser.add_argument('--dry-run', action='store_true', default=False,
                    help='show commands but don\'t execute them')
args = parser.parse_args()


# Load dataset configuration settings
config_file = args.config
if not os.path.exists(config_file):
    raise OSError('Config file not found: ' + config_file)
with open(config_file) as f:
    config = yaml.safe_load(f)

base_paths = config['paths'].split()
dataset_paths = config['datasets'].split()


# print(config)

project = config['project']

path_template = config['DRS'][project]['path']
file_template = config['DRS'][project]['file']

dataset_template = config['DRS'][project]['dataset']
# sep = '.'
# dataset_params = [s.strip('{').strip('}') for s in dataset_template.split(sep)]


datasets = {}
for base_path in base_paths:
    for dataset_path in dataset_paths:
        d = find_datasets(base_path, dataset_path, dataset_template, path_template)
        datasets.update(d)
        del d
# for dataset_id, info in datasets.items():
#     print(dataset_id, info['path'])

print(f'Found {len(datasets)} datasets')

# if filters:
#     assert isinstance(filters, list)
#     assert all([isinstance(d,dict) for d in filters])
#     keep = set()
#     for dataset_id, info in datasets.items():
#         params = info['params']
#         if any([match_params(params, filt) for filt in filters]):
#             keep.add(dataset_id)
#     datasets = {s: datasets[s] for s in keep}

filter = config['keep']
if filter:
    keep = set()
    for dataset_id, info in datasets.items():
        if match_params(info['params'], filter):
            keep.add(dataset_id)
    datasets = {s: datasets[s] for s in keep}


print(f'Retained {len(datasets)} datasets')

datasets = OrderedDict({s : datasets[s] for s in sorted(datasets.keys(), key=str.lower)})


# check stamp of approval


del config
##############################################################################
# The datasets to publish have been determined. 
# Now carry out publishing commands.

# Load configuration settings
config_file = 'config-publisher.yaml'
if not os.path.exists(config_file):
    raise OSError('Config file not found: ' + config_file)
with open(config_file) as f:
    config = yaml.safe_load(f)


if args.mapfile:
    # generate mapfiles
    # these are small files containing info about each dataset to publish, such as its checksum


    env = config['mapfile']['env']

    # check that correct env is active
 


    mapfile_path_template = config['mapfile']['mapfile_subdir']
    mapfile_base_path = config['mapfile']['mapfile_dir']
    if not os.path.exists(mapfile_base_path):
        os.makedirs(mapfile_base_path)

    commands = config['mapfile']['commands']
    for dataset_id, info in datasets.items():
        d = {
            'mapfile_path' : os.path.join(mapfile_base_path, mapfile_path_template.format(**info['params'])),
            'dataset_path' : info['path'],
            'project' : project,
        }
        do_cmds = []
        for cmd in commands:
            do_cmds.append( cmd.format(**d) )

        for cmd in do_cmds:
            print(cmd)


if args.publish:
    # publish to ESGF
    # this assumes that mapfiles have already been generated

    env = config['publish']['env']

    # check that correct env is active
 

    mapfile_path_template = config['mapfile']['mapfile_subdir']
    mapfile_base_path = config['mapfile']['mapfile_dir']

    commands = config['publish']['commands']
    for dataset_id, info in datasets.items():
        mapfile_path = os.path.join(mapfile_base_path, mapfile_path_template.format(**info['params']))
        mapfile = dataset_id + os.path.extsep + 'map'
        d = {
            'mapfile' : os.path.join(mapfile_path, mapfile)
        }

        do_cmds = []
        for cmd in commands:
            do_cmds.append( cmd.format(**d) )


        for cmd in do_cmds:
            print(cmd)

        if not os.path.exists(d['mapfile']):
            print('Mapfile not found: ' + d['mapfile'])
            continue




