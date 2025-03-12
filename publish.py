#!/usr/bin/env python3
'''
Thin wrapper around ESGF publishing software.
Use to publish CCCma datasets to ESGF.

https://esg-publisher.readthedocs.io/en/main/index.html

'''
import argparse
import datetime
import json
import os
import sys
import yaml
from collections import OrderedDict

from tools import find_datasets, get_unique_param_values, match_params, publication_checks
from esgfsearch import search

##############################################################################

datasets_file = 'datasets.json'

parser = argparse.ArgumentParser(
    description='Publish CCCma datasets to ESGF'
    )
parser.add_argument('-c', '--config', type=str, default='config-datasets.yaml',
                    help='name of config file containing datasets to publish, default: %(default)s')
# Define different publishing actions as input flags
actions = OrderedDict({
    'datasets' : {
        'short' : '-d', 
        'help' : 'find datasets to publish and write info on them to ' + datasets_file
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
parser.add_argument('-df', '--datasets-file', type=str, default=datasets_file,
                    help='name of datasets output json file')
parser.add_argument('-nv', '--no-validation', action='store_true', default=False,
                    help='turn off checking of validation list (Stamp of Approval)')
parser.add_argument('-dr', '--dry-run', action='store_true', default=False,
                    help='show commands but don\'t execute them')
parser.add_argument('-nes', '--no-esgf-search', action='store_true', default=False,
                    help='turn off ESGF search that checks whether datasets are already published')
args = parser.parse_args()

if not any([args.__dict__[action] for action in actions]):
    print('Specify at least one of these options (invoke with -h for more info): ')
    for action, d in actions.items():
        print(f'  {d["short"]}, --{action}')
    sys.exit()

if args.datasets_file:
    datasets_file = args.datasets_file

##############################################################################
# Load dataset configuration settings from config file
config_file = args.config
if not os.path.exists(config_file):
    raise OSError('Config file not found: ' + config_file)
with open(config_file) as f:
    config = yaml.safe_load(f)

repo_path = os.environ['REPO_PATH']
if not os.path.exists(repo_path):
    raise ValueError('Path to esgwrapper code repo is required, received: ' + repo_path)

project = config['project']

# Load configuration settings for publishing commands
config_file = os.path.join(repo_path, 'config-publisher.yaml')
if not os.path.exists(config_file):
    raise OSError('Config file not found: ' + config_file)
with open(config_file) as f:
    config_pub = yaml.safe_load(f)

##############################################################################
if args.datasets:
    # Determine datasets to publish, write them to datasets_file

    base_paths = config['paths'].split()  # top-level paths to search at
    dataset_paths = config['datasets'].split()  # datasets to search (dir path for some level in the DRS dir tree)

    dataset_template = config_pub['DRS'][project]['dataset']
    path_template = config_pub['DRS'][project]['path']
    # file_template = config_pub['DRS'][project]['file']

    datasets = {}
    searched_base_paths = []
    for base_path in base_paths:
        if os.path.exists(base_path):
            print('Searching path: ' + base_path)
            searched_base_paths.append(base_path)
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

    filter = config['exclude']
    if filter:
        keep = set()
        for dataset_id, info in datasets.items():
            if not match_params(info['params'], filter):
                keep.add(dataset_id)
        datasets = {s: datasets[s] for s in keep}

    print(f'Retained {len(datasets)} datasets')

    if not args.no_validation:
        # Check stamp of approval and any other validation criteria
        validation_file = os.path.join(repo_path, 'input/validation_variables.json')
        datasets = publication_checks(datasets, validation_file)

    dataset_sep = '.'
    dataset_parameters = [s.strip('{').strip('}') for s in dataset_template.split(dataset_sep)]
    param_unique_values = get_unique_param_values(datasets, dataset_parameters)

    if not args.no_esgf_search:
        # Check which datasets are already published
        index_node = config_pub['search_esgf']['index_node']
        print(f'Checking for already published datasets by searching {index_node}')

        published_datasets = search(param_unique_values, dataset_parameters, project, index_node,
                                    verbose=config_pub['search_esgf']['verbose'],
                                    show_browser_url=config_pub['search_esgf']['show_browser_url'],
                                    keep_params=None,
                                    )

        keep = set(datasets.keys()).difference(set(published_datasets))
        n = len(datasets)
        datasets = {s: datasets[s] for s in keep}
        if len(datasets) == n:
            print('None of the datasets are already published')
        elif len(datasets) == 0:
            print('All of the datasets are already published')
        else:
            print(f'Removed {n-len(datasets)} already-published datasets from publishing list')

    datasets = OrderedDict({s : datasets[s] for s in sorted(datasets.keys(), key=str.lower)})
    param_unique_values = get_unique_param_values(datasets, dataset_parameters)
    if any([len(vals) > 0 for vals in param_unique_values.values()]):
        print('Unique parameter values:')
        for p in dataset_parameters:
            print(f'  {p} : ' + ', '.join(param_unique_values[p]))
    out = OrderedDict({
        'Header' : {
            'date' : datetime.datetime.now().strftime('%d %b %Y'),
            'paths searched' : searched_base_paths,
            'no. of datasets' : len(datasets),
            'unique parameter values' : param_unique_values,
       },
        'datasets' : datasets
    })
    filepath = datasets_file
    with open(filepath, 'w') as f:
        json.dump(out, f, indent=4)
        print(f'Wrote {filepath} with {len(datasets)} datasets')

del config

##############################################################################
if args.mapfile or args.publish:

    # Load info on datasets
    filepath = datasets_file
    with open(filepath, 'r') as f:
        datasets = json.load(f)['datasets']
        print('Loaded ' + filepath)

    do_cmds = not args.dry_run

##############################################################################
if args.mapfile:
    # Generate mapfiles
    # These are small files containing info about each dataset to publish, such as its checksum

    # check that correct env is active
    env = config_pub['mapfile']['conda env']
    if do_cmds and os.environ['CONDA_DEFAULT_ENV'] != env:
        raise OSError('To run commands, first do:\n  conda activate ' + env)

    mapfile_path_template = config_pub['mapfile']['mapfile_subdir']
    mapfile_base_path = config_pub['mapfile']['mapfile_dir']
    if not os.path.exists(mapfile_base_path):
        os.makedirs(mapfile_base_path)

    # Example mapfile name:
    #   CMIP6.DCPP.CCCma.CanESM5.dcppB-forecast.s2022-r1i1p2f1.Amon.tas.gn.v20190429.map
    # It seems to follow the dataset template.
    dataset_template = config_pub['DRS'][project]['dataset']
    mapfile_template = dataset_template + os.path.extsep + 'map'

    commands = config_pub['mapfile']['commands']
    for dataset_id, info in datasets.items():
        d = {
            'mapfile_path' : os.path.join(mapfile_base_path, mapfile_path_template.format(**info['params'])),
            'dataset_path' : info['path'],
            'project' : project,
        }
        if not config_pub['mapfile']['clobber']:
            filename = mapfile_template.format(**info['params'])
            filepath = os.path.join(d['mapfile_path'], filename)
            if os.path.exists(filepath):
                print('Not overwriting existing mapfile: ' + filepath)
                continue

        cmds = []
        for cmd in commands:
            cmds.append( cmd.format(**d) )

        for cmd in cmds:
            print('\n' + cmd)
            if do_cmds:
                os.system(cmd)


##############################################################################
if args.publish:
    # Publish to ESGF
    # (This assumes that mapfiles have already been generated)

    # check that correct env is active
    env = config_pub['publish']['conda env']
    if do_cmds and os.environ['CONDA_DEFAULT_ENV'] != env:
        raise OSError('To run commands, first do:\n  conda activate ' + env)

    mapfile_path_template = config_pub['mapfile']['mapfile_subdir']
    mapfile_base_path = config_pub['mapfile']['mapfile_dir']

    commands = config_pub['publish']['commands']
    for dataset_id, info in datasets.items():
        mapfile_path = os.path.join(mapfile_base_path, mapfile_path_template.format(**info['params']))
        mapfile = dataset_id + os.path.extsep + 'map'
        d = {
            'mapfile' : os.path.join(mapfile_path, mapfile)
        }
        if not os.path.exists(d['mapfile']):
            print('Mapfile not found: ' + d['mapfile'])
            continue

        cmds = []
        for cmd in commands:
            cmds.append( cmd.format(**d) )

        for cmd in cmds:
            print('\n' + cmd)
            if do_cmds:
                os.system(cmd)

