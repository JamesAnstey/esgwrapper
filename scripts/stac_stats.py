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
        published_unapproved = defaultdict(list)
        with open(args.validation) as f:
            d = json.load(f)
            variable_status = d['model']
        other_models = set()
        for dataset_id, info in datasets.items():
            var_name = cmip7_compound_name_from_stac_dataset(info)
            model = info['properties']['cmip7:source_id']
            if model not in variable_status:
                # Presumably this is not a CCCma model
                other_models.add(model)
                continue
            var_info = variable_status[model][var_name]  # if variable is published, it must have an entry
            if var_info['aggregate_status'] != 'approved':
                published_unapproved[var_name].append(dataset_id)
        if len(published_unapproved) == 0:
            models_checked = ', '.join(sorted(variable_status.keys()))
            print(f'All published variables are approved!\n  Models checked: {models_checked}')
        else:
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
