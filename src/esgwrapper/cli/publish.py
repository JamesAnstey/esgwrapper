#!/usr/bin/env python3
'''
Thin wrapper around ESGF publishing software.
Use to publish CCCma datasets to ESGF.

https://esg-publisher.readthedocs.io/en/main/index.html

'''
import argparse
import json
import logging
import os
import requests
import shutil
import subprocess
import sys
import time

from collections import OrderedDict
from datetime import datetime, UTC
from pystac_client import Client

from esgwrapper import CONFIG_FILES
from esgwrapper.utils.tools import (load_config_file,
                                    find_datasets, get_unique_param_values, match_params,
                                    publication_checks,
                                    data_request_checks, get_dreq_validation_file)
from esgwrapper.utils.esgfsearch import search, show_params, parse_file_size_str, file_size_str

##############################################################################

DATE_FORMAT = '%d %b %Y, %H:%M:%S UTC'

DEFAULT_DATASETS_FILE = 'datasets.json'
DEFAULT_INVENTORY_FILE = 'inventory.json'

QC_REPORTS_DIR = 'ccreport'


def check_env(config):
    '''
    Check that correct environment is active.
    List of valid environments is given in config-publisher.yaml.
    '''
    if ('venv' in config) and ('conda env' in config):
        raise ValueError('config-publisher.yaml should specify either venv or conda env, not both')
    if 'venv' in config:
        valid_envs = config['venv']
        valid_envs_realpath = [os.path.realpath(env) for env in valid_envs]
        if 'VIRTUAL_ENV' not in os.environ:
            raise ValueError('No venv is activated')
        if os.environ['VIRTUAL_ENV'] not in valid_envs_realpath:
            msg = ['To run commands, activate one of the valid environments (set in config-publisher.yaml):']
            for env in valid_envs:
                msg.append(f'  {env}')
            msg.append('Example: ')
            cmd = 'source ' + os.path.join(env, 'bin/activate')
            msg.append(f'  {cmd}')
            raise OSError('\n'.join(msg))

    elif 'conda env' in config:
        valid_envs = config['conda env']
        if 'CONDA_DEFAULT_ENV' not in os.environ:
            raise ValueError('No conda env is activated')
        if os.environ['CONDA_DEFAULT_ENV'] not in valid_envs:
            msg = ['To run commands, activate one of the valid environments (set in config-publisher.yaml):']
            for env in valid_envs:
                msg.append(f'  {env}')
            msg.append('Example: ')
            cmd = f'conda activate {env}'
            msg.append(f'  {cmd}')
            raise OSError('\n'.join(msg))

    else:
        raise Exception('Need to specify env to run publishing commands')

def exec_cmds(commands: list[str], cmd_args: dict, do_cmds: bool = True, retries: int = 0) -> list[dict]:
    '''
    Execute list of commands.
    Checks return codes of commands and stops if a command fails.
    If do_cmds=False, the commands that would have been executed are displayed (without running them).

    Arguments
    ---------
    commands: list[str]
        List of command templates. Example of one command template:
        "esgmapfile make --project {project} --outdir {mapfile_path} --directory {dataset_path}"
    cmd_args: dict
        Argument:value pairs to substitute into command templates. Example:
        {'project': 'cmip7'}
    do_cmds: bool
        True ==> execute the commands
        False ==> show the commands that would be executed, but don't execute them
    retries: int
        Number of times to retry a command if it fails.
        retries = 0 ==> only try it once

    Returns
    -------
    exit_status: int
        Exit status of last command executed (0 = success).
    '''
    cmds = []
    for cmd in commands:
        cmds.append( cmd.format(**cmd_args) )

    exit_status = None
    attempt = 1
    max_attempts = 1 + retries
    start_time = time.time()
    cmd_results = []
    for cmd in cmds:
        cmd_result = {'cmd': cmd}
        cmd_results.append(cmd_result)
        if do_cmds:
            while attempt <= max_attempts:
                if attempt > 1:
                    # Show message saying this is a retry
                    print(f'Returned exit status={exit_status}, retrying (attempt {attempt} of {max_attempts})')
                print(cmd)

                # Using subprocess.run works fine but the stdout is not seen by the user
                # result = subprocess.run(cmd.split(), capture_output=True, text=True)
                # exit_status = result.returncode

                # Using subprocess.Popen allows user to see the stdout
                result = subprocess.Popen(
                    cmd.split(),
                    stdout=sys.stdout, # preserves colour (if any) in the stdout
                    stderr=sys.stderr,
                    text=True,
                )
                result.communicate()
                exit_status = result.returncode

                cmd_result.update({'exit_status': exit_status, 'attempt': attempt})
                if exit_status == 0:
                    # Command has succeeded, so exit the retry loop
                    break
                else:
                    # Command failed
                    attempt += 1

            if exit_status != 0:
                # If the command did not ultimately succeed (whether it was tried many times or just once),
                # don't attempt subsequent commands (if any).
                cmd_result['time_taken'] = time.time() - start_time
                break

        else:
            # Show command that would have been executed
            print(cmd)
            cmd_result.update({'exit_status': 'N/A', 'attempt': 0})

        # Record time taken to complete the command (units: seconds)
        cmd_result['time_taken'] = time.time() - start_time

    return cmd_results

def log_cmds(dataset_id: str, cmd_results: dict) -> str:
    '''
    Write success/fail status of commands.
    '''
    msg = []
    for cmd_result in cmd_results:
        msg += [cmd_result['cmd']]
        exit_status, attempt = cmd_result['exit_status'], cmd_result['attempt']
        time_taken = str('%.4f' % cmd_result['time_taken'])
        details = f'exit_status: {exit_status}, attempts: {attempt}, time: {time_taken} s'
        if cmd_result['exit_status'] == 0:
            msg += [f'SUCCESS - {details}']
        else:
            msg += [f'FAIL - {details}']
    msg = [f'   {s}' for s in msg]
    return msg

def parse_args():

    parser = argparse.ArgumentParser(
        description='Publish CCCma datasets to ESGF'
        )

    parser.add_argument('-c', '--config', type=str, default='config-datasets.yaml',
                        help='name of config file containing datasets to publish, default: %(default)s')

    # Define different publishing actions as input flags
    actions = OrderedDict({
        'inventory': {
            'short': '-i',
            'help': f'inventory datasets and write info on them to json file (default: {DEFAULT_INVENTORY_FILE})'
        },
        'datasets': {
            'short': '-d',
            'help': f'from inventory find datasets to publish and write info on them to json file (default: {DEFAULT_DATASETS_FILE})'
        },
        'mapfile': {
            'short': '-m',
            'help': 'generate mapfiles'
        },
        'publish': {
            'short': '-p',
            'help': 'publish to ESGF'
        },
    })
    for action, d in actions.items():
        parser.add_argument(d['short'], f'--{action}', action='store_true', default=False, help=d['help'])

    parser.add_argument('-dry', '--dry-run', action='store_true', default=False,
                        help='show commands but don\'t execute them')
    parser.add_argument('-mc', '--mapfile-clobber', action='store_true', default=False,
                        help='overwrite mapfile if it already exists')

    parser.add_argument('-max', '--max-size', type=str,
                        help='maximum size of dataset to retain, examples: "1 GB", 1GB, 1G')
    parser.add_argument('-min', '--min-size', type=str,
                        help='minimum size of dataset to retain, examples: "1 GB", 1GB, 1G')
    parser.add_argument('-nxr', '--no-xarray', action='store_true', default=False,
                        help='use --no-xarray argument to esgpublish (prevents failure on large datasets)')

    parser.add_argument('-if', '--inventory-file', type=str, default=DEFAULT_INVENTORY_FILE,
                        help='name of inventory output json file')
    parser.add_argument('-df', '--datasets-file', type=str, default=DEFAULT_DATASETS_FILE,
                        help='name of datasets output json file')

    parser.add_argument('-nesgf', '--no-esgf-search', action='store_true', default=False,
                        help='turn off ESGF search that checks whether datasets are already published')
    parser.add_argument('-ndreq', '--no-data-request', action='store_true', default=False,
                        help='turn off filtering based on the data request')
    parser.add_argument('-nval', '--no-validation', action='store_true', default=False,
                        help='turn off checking of validation list (Stamp of Approval) - use with caution!')

    parser.add_argument('-r', '--retries', type=int, default=0,
                        help='number of times to retry publishing command if it fails (default: 0)')
    parser.add_argument('-s', '--start', type=int,
                        help='index to begin with in list of datasets (0 = first dataset)')
    parser.add_argument('-n', '--number', type=int,
                        help='number of datasets to use from list of datasets (default: all)')
    parser.add_argument('-id', '--dataset-ids', type=str,
                        help='dataset ids to use: comma-separated list, or file listing datasets')

    parser.add_argument('-c7', '--cmip7-dev', action='store_true', default=False,
                        help='TEMPORARY option for use with -d for CMIP7 ESGF-NG publishing')
    parser.add_argument('-api', '--api-method', type=int, default=3,
                        help='TEMPORARY specify how to use restful api to find out what datasets are already published')

    parser.add_argument('-ne', '--no-env', action='store_true', default=False,
                        help='disable environment check (user must sure correct env is activated)')

    args = parser.parse_args()

    if not any([args.__dict__[action] for action in actions]):
        print('Specify at least one of these options (invoke with -h for more info): ')
        for action, d in actions.items():
            print(f'  {d["short"]}, --{action}')
        sys.exit()

    return args


def main():
    args = parse_args()

    if args.inventory_file:
        inventory_file = args.inventory_file
    if args.datasets_file:
        datasets_file = args.datasets_file

    logger = logging.getLogger('esgwrapper')
    date_run = datetime.now(UTC)
    date_run_str = date_run.strftime('%Y.%m.%d_%H.%M.%S_UTC')
    logfile = f'esgwrapper_{date_run_str}.log'


    logfile = 'testing.log'


    # logging.basicConfig(filename=logfile, filemode='w', level=logging.INFO)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(logfile, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    date_run_str = date_run.strftime('%b %d %Y, %H:%M:%S UTC')
    logger.info(f' Starting publish.py at {date_run_str}')

    get_size = True

    # Load dataset configuration settings from config file
    config_dat = load_config_file(args.config)
    project = config_dat['project']

    config_pub = load_config_file(CONFIG_FILES / 'config-publisher.yaml')
    dataset_template = config_pub['DRS'][project]['dataset']

    if args.mapfile_clobber:
        mapfile_clobber = True
    else:
        mapfile_clobber = config_pub['mapfile']['clobber']

    if args.inventory:
        # Determine datasets to publish, write them to datasets_file

        if args.max_size:
            max_size = parse_file_size_str(args.max_size)
        if args.min_size:
            min_size = parse_file_size_str(args.min_size)

        base_paths = config_dat['paths']  # top-level paths to search at
        dataset_paths = config_dat['inventory']  # datasets to search (dir path for some level in the DRS dir tree)

        path_template = config_pub['DRS'][project]['path']
        file_template = config_pub['DRS'][project]['file']  # not currently needed (but might be for some projects?)

        datasets = {}
        searched_base_paths = []
        for base_path in base_paths:
            if os.path.exists(base_path):
                print('Searching base path: ' + base_path)
                searched_base_paths.append(base_path)
            else:
                print('Base path not found: ' + base_path)
            for dataset_path in dataset_paths:
                print('Searching path (relative to base path): ' + dataset_path)
                d = find_datasets(project,
                                  base_path, dataset_path,
                                  dataset_template, path_template, file_template,
                                  get_size=get_size)
                datasets.update(d)
                del d

        datasets = OrderedDict({s : datasets[s] for s in sorted(datasets.keys(), key=str.lower)})

        dataset_sep = '.'
        dataset_parameters = [s.strip('{').strip('}') for s in dataset_template.split(dataset_sep)]
        param_unique_values = get_unique_param_values(datasets, dataset_parameters)
        if any([len(vals) > 0 for vals in param_unique_values.values()]):
            print('Unique parameter values:')
            for p in dataset_parameters:
                print(f'  {p} : ' + ', '.join(param_unique_values[p]))
        out = OrderedDict({
            'Header' : {
                'date of inventory': datetime.now(UTC).strftime(DATE_FORMAT),
                'base paths searched': searched_base_paths,
                'dataset paths searched': dataset_paths,
                'no. of datasets found': len(datasets),
                'unique parameter values': param_unique_values,
        },
            'datasets' : datasets
        })
        print(f'Found {len(datasets)} datasets')
        filepath = inventory_file
        with open(filepath, 'w') as f:
            json.dump(out, f, indent=4)
            print(f'Wrote {filepath} with {len(datasets)} datasets')


    ##############################################################################
    if args.datasets:
        # Load inventory
        filepath = inventory_file
        with open(filepath, 'r') as f:
            datasets = json.load(f)['datasets']
            print('Loaded ' + filepath)

        # Set flags that determine what gets done below
        search_esgf = not args.no_esgf_search
        check_data_request = not args.no_data_request
        do_validation = not args.no_validation
        search_esgf_ng = False
        if args.cmip7_dev:
            # TODO: revise all of this to make these choices less ad-hoc
            search_esgf = False
            check_data_request = False
            do_validation = False
            search_esgf_ng = True

        # Apply filters from the config-datasets file
        config_dat = {'keep':{}, 'exclude':{}} | config_dat
        if config_dat['keep']:
            print('Keeping datasets with these parameter values:')
            show_params(config_dat['keep'], indent='  ')
            keep = set()
            for dataset_id, info in datasets.items():
                matches = match_params(info['params'], config_dat['keep'])
                if all(matches.values()):
                    keep.add(dataset_id)
            n = len(datasets)
            datasets = {s: datasets[s] for s in keep}
            print(f'  --> excluded {n-len(datasets)} datasets')
        if config_dat['exclude']:
            print('Excluding datasets with these parameter values:')
            show_params(config_dat['exclude'], indent='  ')
            exclude = set()
            for dataset_id, info in datasets.items():
                matches = match_params(info['params'], config_dat['exclude'])
                if any(matches.values()):
                    exclude.add(dataset_id)
            n = len(datasets)
            datasets = {s: datasets[s] for s in datasets if s not in exclude}
            print(f'  --> excluded {n-len(datasets)} datasets')

        print(f'Retained {len(datasets)} datasets')

        # Filter based on dataset size
        if args.max_size:
            print(f'Keeping datasets with size up to {args.max_size} ({max_size} B)')
            keep = set()
            for dataset_id, info in datasets.items():
                if info['size (bytes)'] <= max_size:
                    keep.add(dataset_id)
            n = len(datasets)
            datasets = {s: datasets[s] for s in keep}
            print(f'  --> excluded {n-len(datasets)} datasets')
        if args.min_size:
            print(f'Keeping datasets with size at least {args.min_size} ({min_size} B)')
            keep = set()
            for dataset_id, info in datasets.items():
                if info['size (bytes)'] >= min_size:
                    keep.add(dataset_id)
            n = len(datasets)
            datasets = {s: datasets[s] for s in keep}
            print(f'  --> excluded {n-len(datasets)} datasets')

        # Ensure datasets with size zero and/or no files are discarded
        if get_size:
            exclude = set()
            for dataset_id, info in datasets.items():
                if info['size (bytes)'] == 0 or info['no. of files'] == 0:
                    exclude.add(dataset_id)
            if len(exclude) > 0:
                n = len(datasets)
                keep = [s for s in datasets if s not in exclude]
                datasets = {s: datasets[s] for s in keep}
                print(f'  --> excluded {n-len(datasets)} datasets that had zero size and/or no valid files')

        # Filter based on other criteria
        if do_validation:
            # Check stamp of approval and other validation criteria
            validation_file = os.path.join(repo_path, 'input/validation_variables.json')
            datasets = publication_checks(datasets, validation_file)
        else:
            print('WARNING: data validation (Stamp of Approval) filtering is off')
        if check_data_request:
            # Check which datasets are requested in the project's data request, exclude those that aren't
            validation_file = get_dreq_validation_file(project, repo_path)
            datasets = data_request_checks(datasets, validation_file)
        else:
            print('WARNING: data request filtering is off')

        dataset_sep = '.'
        dataset_parameters = [s.strip('{').strip('}') for s in dataset_template.split(dataset_sep)]
        param_unique_values = get_unique_param_values(datasets, dataset_parameters)

        if search_esgf:
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
                print(f'Removed {n-len(datasets)} already-published datasets from publishing list (keeping {len(datasets)})')

        if search_esgf_ng:
            # # Check which datasets are already published by searching ESGF-NG.
            # # TODO: figure out whether or not this should replace the above search_esgf call.

            # index_node = config_pub['search_esgf_ng']['index_node']
            # print(f'Checking for already published datasets by searching {index_node}')

            # published_datasets = search_ng(param_unique_values, dataset_parameters, project, index_node,
            #                             # verbose=config_pub['search_esgf']['verbose'],
            #                             # show_browser_url=config_pub['search_esgf']['show_browser_url'],
            #                             # keep_params=None,
            #                             )



            # Temporary option (Aug 2026) while figuring out best way to query ESGF-NG via api.
            #
            # The assumption here is that if a dataset is already published, a URL will exist of the form:
            #   https://discovery.{where}.esgf.io/collections/CMIP7/items/{dataset_id}
            # Example:
            #   https://discovery.east.esgf.io/collections/CMIP7/items/MIP-DRS7.CMIP7.CMIP.CCCma.CanESM5-1.piControl.r1i1p2f1.glb.mon.uas.tavg-h10m-hxy-u.g120.v20190429
            #
            # Use this to determine what's already published.
            if search_esgf:
                raise Exception('this is a stopgap for proper ESGF search')
            index_node = 'east'
            # index_node = 'west'

            keep = []

            if args.api_method == 1:
                for dataset_id in datasets:
                    url = f'https://discovery.{index_node}.esgf.io/collections/CMIP7/items/{dataset_id}'
                    response = requests.get(url).json()
                    # print(url)
                    if 'code' in response:
                        if response['code'] == "NotFoundError":
                            # Dataset was not found, therefore is not already published
                            keep.append(dataset_id)

                            # Example of returned json:
                            #{"code":"NotFoundError","description":"Item MIP-DRS7.CMIP7.CMIP.CCCma.CanESM5-1.piControl.r1i1p2f1.glb.mon.boovas.tavg-h10m-hxy-u.g120.v20190429 does not exist inside Collection CMIP7"}'

                datasets = {s: datasets[s] for s in keep}
                del keep

            elif args.api_method == 2:
                limit = 10000000000 # set large enough to get all datasets on ESGF

                limit = str(limit)
                url = f'https://discovery.east.esgf.io/collections/CMIP7/items?fields=id,properties.retracted&limit={limit}'
                print(f'Checking for already-published datasets by searching:\n  {url}')
                response = requests.get(url).json()

                outfile = 'published_datasets.json'
                with open(outfile, 'w') as f:
                    json.dump(response, f, indent=2)
                    print('Wrote ' + outfile)

                # Get list of published dataset id's
                exclude = []
                for d in response['features']:
                    dataset_id = d['id']
                    retracted = bool(d['properties']['retracted'])
                    if not retracted:
                        exclude.append(dataset_id)

                datasets = {s: datasets[s] for s in datasets if s not in exclude}
                del exclude

            elif args.api_method == 3:
                # Use STAC API
                url_endpoint = f"https://discovery.{index_node}.esgf.io"
                client = Client.open(url_endpoint)
                print(f'Searching ESGF-NG using STAC API for endpoint: {url_endpoint}')
                exclude = set()
                for source_id in param_unique_values['source_id']:
                    for experiment_id in param_unique_values['experiment_id']:
                        query = {
                            'collections': [project.upper()],
                            'query': {
                                f'{project}:source_id': {"eq": source_id},
                                f'{project}:experiment_id': {"eq": experiment_id},
                            }
                        }
                        search = client.search(**query)
                        items = search.item_collection()
                        dataset_ids = [item.id for item in items]
                        print(f'  Found {len(dataset_ids)} published datasets for source_id={source_id} and experiment_id={experiment_id}')
                        exclude.update(dataset_ids)
                        del dataset_ids
                print(f'  TOTAL no. of published datasets: {len(exclude)}')
                datasets = {s: datasets[s] for s in datasets if s not in exclude}

                exclude = sorted(exclude, key=str.lower)
                outfile = 'published_datasets.txt'
                w = '\n'.join(exclude) + '\n'
                with open(outfile, 'w') as f:
                    f.write(w)
                    print(f'Wrote {outfile} listing {len(exclude)} published datasets')
                del exclude

            else:
                raise ValueError(f'Which ad-hoc API method should be used?')


            if len(datasets) == n:
                print('None of the datasets are already published')
            elif len(datasets) == 0:
                print('All of the datasets are already published')
            else:
                print(f'Removed {n-len(datasets)} already-published datasets from publishing list (keeping {len(datasets)})')

        datasets = OrderedDict({s : datasets[s] for s in sorted(datasets.keys(), key=str.lower)})
        param_unique_values = get_unique_param_values(datasets, dataset_parameters)
        if any([len(vals) > 0 for vals in param_unique_values.values()]):
            print('Unique parameter values:')
            for p in dataset_parameters:
                print(f'  {p} : ' + ', '.join(param_unique_values[p]))
        out = OrderedDict({
            'Header' : {
                'date of search' : datetime.now(UTC).strftime(DATE_FORMAT),
                'inventory file' : inventory_file,
                'no. of datasets retained' : len(datasets),
                'unique parameter values' : param_unique_values,
        },
            'datasets' : datasets
        })
        if get_size:
            # Report total size of datasets
            size = 0
            for dataset_id, info in datasets.items():
                size += info['size (bytes)']
            total_size = file_size_str(size)
            out['Header'].update({
                'total size (all datasets)': total_size
            })
            msg = f'Total size of publishable datasets: {total_size}'
            if args.inventory:
                msg = f'Total size of inventoried datasets: {total_size}'
            print(msg)
        filepath = datasets_file
        with open(filepath, 'w') as f:
            json.dump(out, f, indent=4)
            print(f'Wrote {filepath} with {len(datasets)} datasets')


    # config_dat is not used after this point since all info on datasets to be published
    # should be in the output json file datasets_file.
    del config_dat

    ##############################################################################
    if args.mapfile or args.publish:

        # Load info on datasets to publish
        filepath = datasets_file
        with open(filepath, 'r') as f:
            datasets = json.load(f)['datasets']
            print('Loaded ' + filepath)

        dataset_ids = sorted(datasets.keys(), key=str.lower)

        if args.dataset_ids:
            if os.path.exists(args.dataset_ids):
                with open(args.dataset_ids) as f:
                    dataset_ids = f.readlines()
            else:
                dataset_ids = args.dataset_ids.split(',')
            dataset_ids = [s.strip() for s in dataset_ids]

        if args.start:
            dataset_ids = dataset_ids[args.start:]
        if args.number:
            dataset_ids = dataset_ids[:args.number]

        datasets = OrderedDict({s : datasets[s] for s in dataset_ids})
        del dataset_ids

        do_cmds = not args.dry_run

    ##############################################################################
    if args.mapfile:
        # Generate mapfiles. These are small files containing info about each dataset,
        # including the checksums of its files.

        if do_cmds and not args.no_env:
            # Check that correct env is activated
            check_env(config_pub['mapfile'])

        # Get info to construct mapfile paths
        mapfile_path_template = config_pub['mapfile']['mapfile_subdir'][project]
        mapfile_base_path = config_pub['mapfile']['mapfile_dir']
        if not os.path.exists(mapfile_base_path):
            os.makedirs(mapfile_base_path)

        # Get mapfile template, used to determine if a mapfile already exists
        dataset_template = config_pub['DRS'][project]['dataset']
        mapfile_template = dataset_template + os.path.extsep + 'map'
        # Example mapfile name for CMIP6:
        #   CMIP6.DCPP.CCCma.CanESM5.dcppB-forecast.s2022-r1i1p2f1.Amon.tas.gn.v20190429.map

        # Get command template(s)
        commands = config_pub['mapfile']['commands']

        # Loop over datasets to create a mapfile for each one
        n = len(datasets)
        k = 0
        for dataset_id, info in datasets.items():
            k += 1
            logger.info(f' Generating mapfile for dataset ({k} of {n}): {dataset_id} ({info["size (human readable)"]})')
            cmd_args = {
                'mapfile_path' : os.path.normpath(os.path.join(
                    mapfile_base_path, mapfile_path_template.format(**info['params'])
                    )),
                'dataset_path' : info['path'],
                'project' : project,
            }
            if not mapfile_clobber:
                filename = mapfile_template.format(**info['params'])
                filepath = os.path.join(cmd_args['mapfile_path'], filename)
                if os.path.exists(filepath):
                    print('Not overwriting existing mapfile: ' + filepath)
                    continue

            # Run commands to generate mapfile for this dataset
            cmd_results = exec_cmds(commands, cmd_args, do_cmds)

            if do_cmds or True:
                # Write logfile summarizing the results of commands
                for msg in log_cmds(dataset_id, cmd_results):
                    logger.info(msg)

    ##############################################################################
    if args.publish:
        # Publish to ESGF. This assumes that mapfiles have already been generated.

        if do_cmds and not args.no_env:
            # Check that correct env is activated
            check_env(config_pub['publish'])

        # Get info to construct mapfile paths
        mapfile_path_template = config_pub['mapfile']['mapfile_subdir'][project]
        mapfile_base_path = config_pub['mapfile']['mapfile_dir']

        # Get command template(s)
        commands = config_pub['publish']['commands']
        if args.no_xarray:
            # Convenience option to add --no-xarray argument to esgpublish command.
            # Intention of this wrapper is that publisher command(s) are set in config-publisher.yaml.
            # However we only need to use --no-xarray for large datasets, so it's useful
            # to be able to specify it as a command-line argument to publish.py instead
            # of modifying config-publisher.yaml often (error-prone) or having more than
            # one config-publisher.yaml (confusing). Can use in conjuntion with -min argument.
            for k,cmd in enumerate(commands):
                if cmd.startswith('esgpublish'):
                    commands[k] = cmd + ' --no-xarray'

        # Loop over datasets to publish each one
        n = len(datasets)
        k = 0
        for dataset_id, info in datasets.items():
            k += 1
            print(f'\nPublishing dataset ({k} of {n}): {dataset_id} ({info["size (human readable)"]})')

            # Find mapfile for this dataset
            mapfile_path = os.path.join(mapfile_base_path, mapfile_path_template.format(**info['params']))
            mapfile = dataset_id + os.path.extsep + 'map'
            cmd_args = {
                'mapfile' : os.path.normpath(os.path.join(mapfile_path, mapfile))
            }
            if not os.path.exists(cmd_args['mapfile']):
                print('Mapfile not found: ' + cmd_args['mapfile'])
                continue

            # Run commands to publish this dataset
            cmd_results = exec_cmds(commands, cmd_args, do_cmds, retries=args.retries)

            if do_cmds:
                # Write logfile summarizing the results of commands
                for msg in log_cmds(dataset_id, cmd_results):
                    logger.info(msg)

            # If QC report output file was created, move it to a subdir
            qc_report_file = f'{dataset_id}.ccreport'
            if os.path.exists(qc_report_file):
                if not os.path.exists(QC_REPORTS_DIR):
                    os.makedirs(QC_REPORTS_DIR)
                shutil.move(qc_report_file, os.path.join(QC_REPORTS_DIR, qc_report_file))

    print(f'\nWrote logfile: {logfile}')

if __name__ == '__main__':
    main()
