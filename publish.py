#!/usr/bin/env python
'''
Thin wrapper around ESGF publishing software.

https://esg-publisher.readthedocs.io/en/main/index.html

'''


import argparse
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
parser.add_argument('-nv', '--no-validation', action='store_true', default=False,
                    help='turn off checking of validation list (Stamp of Approval)')
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


project = config['project']

path_template = config['DRS'][project]['path']
file_template = config['DRS'][project]['file']

dataset_template = config['DRS'][project]['dataset']


datasets = {}
for base_path in base_paths:
    for dataset_path in dataset_paths:
        d = find_datasets(base_path, dataset_path, dataset_template, path_template)
        datasets.update(d)
        del d

print(f'Found {len(datasets)} datasets')

filter = config['keep']
if filter:
    keep = set()
    for dataset_id, info in datasets.items():
        if match_params(info['params'], filter):
            keep.add(dataset_id)
    datasets = {s: datasets[s] for s in keep}


print(f'Retained {len(datasets)} datasets')

# Check stamp of approval
if not args.no_validation:
    filepath = 'input/validation_variables.json'
    with open(filepath, 'r') as f:
        validation_vars = json.load(f)['variables']
        print('Loaded ' + filepath)
    # sanitize
    re_key = {'Stamp of\nApproval' : 'Stamp of Approval'}
    for var_info in validation_vars.values():
        for old,new in re_key.items():
            if old in var_info:
                assert new not in var_info, 'existing key: ' + new
                var_info[new] = var_info[old]
                var_info.pop(old)

    check = []
    check.append('Stamp of Approval')

    var_info_key = '{table_id}.{variable_id}'
    keep = set()
    for dataset_id, info in datasets.items():

        var_key = var_info_key.format(**info['params'])
        if var_key not in validation_vars:
            raise ValueError(f'Variable not found in {filepath}: {var_key}')
        var_info = validation_vars[var_key]

        # Do the checks for each dataset
        for p in check:
            if p == 'Stamp of Approval':
                if var_info[p].lower().strip() in ['x']:
                    keep.add(dataset_id)
            else:
                raise ValueError('Unknown check: ' + p)

    datasets = {s: datasets[s] for s in keep}
    print(f'Retained {len(datasets)} datasets after these validation checks: ' + ', '.join(check))


datasets = OrderedDict({s : datasets[s] for s in sorted(datasets.keys(), key=str.lower)})



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




