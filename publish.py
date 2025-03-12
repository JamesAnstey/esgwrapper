#!/usr/bin/env python
'''
Thin wrapper around ESGF publishing software.

https://esg-publisher.readthedocs.io/en/main/index.html

'''
import argparse
import datetime
import json
import os
import sys
import yaml
from collections import OrderedDict

from tools import find_datasets, match_params, publication_checks


parser = argparse.ArgumentParser(
    description='Publish CCCma datasets to ESGF'
    )
parser.add_argument('-c', '--config', type=str, default='config-datasets.yaml',
                    help='name of config file containing datasets to publish, default: %(default)s')
# Define different publishing actions as input flags
actions = OrderedDict({
    'datasets' : {
        'short' : '-d', 
        'help' : 'find datasets to publish and write info on them to datasets.json'
    },
    'mapfile' : {
        'short' : '-m',
        'help' : 'generate mapfiles'
    },
    'publish' : {
        'short' : '-p',
        'help' : 'publish to ESGF'
    }
})
for action, d in actions.items():
    parser.add_argument(d['short'], f'--{action}', action='store_true', default=False, help=d['help'])
# Additional arguments
parser.add_argument('-nv', '--no-validation', action='store_true', default=False,
                    help='turn off checking of validation list (Stamp of Approval)')
parser.add_argument('--dry-run', action='store_true', default=False,
                    help='show commands but don\'t execute them')
args = parser.parse_args()

if not any([args.__dict__[action] for action in actions]):
    print('Specify at least one of these options (invoke with -h for more info): ')
    for action, d in actions.items():
        print(f'  {d["short"]}, --{action}')
    sys.exit()

# Load dataset configuration settings from config file
config_file = args.config
if not os.path.exists(config_file):
    raise OSError('Config file not found: ' + config_file)
with open(config_file) as f:
    config = yaml.safe_load(f)

repo_path = config['repo_path']
if not os.path.exists(repo_path):
    raise ValueError('Path to esgwrapper code repo is required, received: ' + repo_path)

project = config['project']

if args.datasets:

    base_paths = config['paths'].split()  # top-level paths to search at
    dataset_paths = config['datasets'].split()  # datasets to search (dir path for some level in the DRS dir tree)

    dataset_template = config['DRS'][project]['dataset']
    path_template = config['DRS'][project]['path']
    # file_template = config['DRS'][project]['file']

    datasets = {}
    for base_path in base_paths:
        if os.path.exists(base_path):
            print('Searching path: ' + base_path)
        else:
            print('Path not found: ' + base_path)
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

    # Check stamp of approval and any other validation criteria
    if not args.no_validation:
        validation_file = os.path.join(repo_path, 'input/validation_variables.json')
        datasets = publication_checks(datasets, validation_file)


    datasets = OrderedDict({s : datasets[s] for s in sorted(datasets.keys(), key=str.lower)})

    dataset_sep = '.'
    dataset_parameters = [s.strip('{').strip('}') for s in dataset_template.split(dataset_sep)]
    param_unique_values = OrderedDict()
    print('Unique parameter values:')
    for p in dataset_parameters:
        param_unique_values[p] = sorted(set([d['params'][p] for d in datasets.values()]), key=str.lower)
        print(f'  {p} : ' + ', '.join(param_unique_values[p]))

    out = OrderedDict({
        'Header' : {
            'date' : datetime.datetime.now().strftime('%d %b %Y'),
            'top-level paths' : base_paths,
            'no. of datasets' : len(datasets),
            'unique parameter values' : param_unique_values,
       },
        'datasets' : datasets
    })
    filepath = 'datasets.json'
    with open(filepath, 'w') as f:
        json.dump(out, f, indent=4)
        print(f'Wrote {filepath} with {len(datasets)} datasets')

del config
##############################################################################
# The datasets to publish have been determined. 
# Now carry out publishing commands.

if args.mapfile or args.publish:

    # Load configuration settings
    config_file = os.path.join(repo_path, 'config-publisher.yaml')
    if not os.path.exists(config_file):
        raise OSError('Config file not found: ' + config_file)
    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Load info on datasets
    filepath = 'datasets.json'
    with open(filepath, 'r') as f:
        datasets = json.load(f)['datasets']
        print('Loaded ' + filepath)

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


