#!/usr/bin/env python
'''
Load dict returned by stac search and summarie contents
'''

import argparse
import json

from collections import defaultdict, OrderedDict
from textwrap import dedent

from esgwrapper import CONFIG_FILES_DIR
from esgwrapper.utils.esgfsearch import file_size_str

VALIDATION_FILE = CONFIG_FILES_DIR / 'validation_info' / 'validation_status.json'

def parse_args():
    parser = argparse.ArgumentParser(
        description='Summarize STAC search results'
    )

    parser.add_argument('input', type=str,
                        help='json file with search results')

    parser.add_argument('-m', '--model', action='store_true',
                        help='display stats by model')
    parser.add_argument('-v', '--validation', type=str, default=VALIDATION_FILE,
                        help='json file with variable validation statuses to check against published variables')

    return parser.parse_args()

def cmip7_compound_name_from_stac_dataset(info):
    template = '{realm}.{variable_id}.{branding_suffix}.{frequency}.{region}'
    params = {
        'realm': info['properties']['cmip7:realm'][0],
        'variable_id': info['properties']['cmip7:variable_id'],
        'branding_suffix': info['properties']['cmip7:variable_branding_suffix'],
        'frequency': info['properties']['cmip7:frequency'],
        'region': info['properties']['cmip7:region'],
    }
    return template.format(**params)

def main():
    args = parse_args()

    get_model_stats = args.model
    if get_model_stats:
        model_stats = {}

    with open(args.input) as f:
        d = json.load(f)
        datasets = d['datasets']

    n = len(datasets)
    total_size = 0
    for dataset_id, info in datasets.items():
        total_size += info['properties']['size']

        if get_model_stats:
            model = info['properties']['cmip7:source_id']
            if model not in model_stats:
                model_stats[model] = {'total size': 0, 'no. datasets': 0}
            model_stats[model]['total size'] += info['properties']['size']
            model_stats[model]['no. datasets'] += 1

    total_size_str = file_size_str(total_size)
    msg = dedent(f'''
    Number of datasets: {n}
    Total size: {total_size} bytes, {total_size_str}
    ''')
    print(msg)

    if get_model_stats:
        for model, stats in model_stats.items():
            total_size = stats['total size']
            total_size_str = file_size_str(total_size)
            n = stats['no. datasets']
            msg = dedent(f'''\
                {model}:
                    Number of datasets: {n}
                    Total size: {total_size} bytes, {total_size_str}
                ''')
            print(msg)

    if args.validation:
        # Check validation status of published variables
        published_unapproved = defaultdict(list)
        published_older_version = defaultdict(list)
        published_newer_version = defaultdict(list)

        # Load validation status json file, which is produced by get_validation_statuses.py
        with open(args.validation) as f:
            d = json.load(f)
            print(f'Loaded validation statuses from:\n  {args.validation}')
            variable_status = d['model']

        # Loop over datasets found in the stac search
        other_models = set()
        for dataset_id, info in datasets.items():
            var_name = cmip7_compound_name_from_stac_dataset(info)
            model = info['properties']['cmip7:source_id']
            if model not in variable_status:
                # Presumably this is not a CCCma model, since CCCma models should be accounted
                # for in the validation status json file.
                other_models.add(model)
                continue
            # Get validation status for this variable. If variable is published then it must have
            # been approved in the A4D validation system, hence it must have an entry in the
            # validation status json file.
            if var_name not in variable_status[model]:
                # If a published variable doesn't have an entry in the validation status file then
                # something somewhere has gone very wrong.
                raise ValueError(f'\n *** Published variable {var_name} for {model} \
                                 is not in the validation status table! ***\n')
            var_info = variable_status[model][var_name]

            # Check if the published variable has an "approved" status recorded in the validation database
            if var_info['aggregate_status'] != 'approved':
                published_unapproved[var_name].append(dataset_id)

            # Check if the published variable has a version identifier (e.g. "v20190429") that agrees
            # with the one recorded in the validation database
            if 'version' in var_info:
                dataset_version = info['properties']['version']
                if not dataset_version.startswith('v'):
                    dataset_version = 'v' + dataset_version
                assert dataset_version.count('v') == 1
                if dataset_version != var_info['version']:
                    # Dataset is published for a different version than the one in the validation database
                    if dataset_version > var_info['version']:
                        published_newer_version[var_name].append(dataset_id)
                    elif dataset_version < var_info['version']:
                        published_older_version[var_name].append(dataset_id)
                    else:
                        raise Exception(f'dataset version new/old comparison failed on {model} {var_name}: ' +
                                        f'{dataset_version}, {var_info["version"]}')

        models_checked = ', '.join(sorted(variable_status.keys()))
        print(f'Models checked for validation statuses: {models_checked}')


        if len(published_unapproved) > 0:
            # Variables that were published but are not recorded as approved in the validation database
            nv = len(published_unapproved)
            nd = sum([len(dataset_ids) for dataset_ids in published_unapproved.values()])
            print(f'{nv} variables for {nd} datasets are published but NOT APPROVED in the validation database')
            outfile = 'published_unapproved.json'
            with open(outfile, 'w') as f:
                json.dump(published_unapproved, f, indent=4)
                print(f'  Wrote {outfile}')
        else:
            print('All published variables are APPROVED in the validation database')

        if len(published_newer_version) > 0:
            # Variables that were published at a version newer than the one in the validation database
            nv = len(published_newer_version)
            nd = sum([len(dataset_ids) for dataset_ids in published_newer_version.values()])
            print(f'Published version of {nv} variables for {nd} datasets is NEWER than the validation database version')
            outfile = 'published_newer_version.json'
            with open(outfile, 'w') as f:
                json.dump(published_newer_version, f, indent=4)
                print(f'  Wrote {outfile}')
        else:
            print('No published variables have version NEWER than the validation database version')

        if len(published_older_version) > 0:
            # Variables that were published at a version older than the one in the validation database
            nv = len(published_older_version)
            nd = sum([len(dataset_ids) for dataset_ids in published_older_version.values()])
            print(f'Published version of {nv} variables for {nd} datasets is OLDER than the validation database version')
            outfile = 'published_older_version.json'
            with open(outfile, 'w') as f:
                json.dump(published_older_version, f, indent=4)
                print(f'  Wrote {outfile}')
        else:
            print('No published variables have version OLDER than the validation database version')

        write_retraction_lists = len(published_unapproved) > 0

        if write_retraction_lists:
            retract_vars = OrderedDict()
            retract_datasets = []
            for var_name in sorted(published_unapproved.keys(), key=str.lower):
                dataset_ids = sorted(published_unapproved[var_name])
                assert len(dataset_ids) == len(set(dataset_ids))
                retract_vars[var_name] = dataset_ids
                retract_datasets += dataset_ids
            assert len(retract_datasets) == len(set(retract_datasets))

            nd = len(retract_datasets)
            nv = len(retract_vars)
            out = OrderedDict({
                'Header': OrderedDict({
                    'No. of datasets to retract': nd,
                    'No. of variables to retract': nv
                }),
                'retract': retract_vars
            })
            outfile = 'retract_variables.json'
            with open(outfile, 'w') as f:
                json.dump(out, f, indent=4)
                print(f'Wrote {outfile} with {nv} variables for {nd} datasets')
            outfile = 'retract_datasets.txt'
            with open(outfile, 'w') as f:
                f.write('\n'.join(retract_datasets))
                print(f'Wrote {outfile} with {nd} datasets')
        if len(other_models) > 0:
            models_not_checked = ', '.join(sorted(other_models))
            print(f'These models were found in the search but have no validation status available:\n  {models_not_checked}')

if __name__ == '__main__':
    main()
