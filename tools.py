#!/usr/bin/env python

import json
import os


def match_params(params, reference):
    keep = True
    for p in reference:
        if p in params:
            # keep = keep and ( params[p] in reference[p] )
            if isinstance(reference[p], str):
                values = [reference[p]]
            else:
                values = reference[p]
            assert isinstance(values, list)
            assert all( [isinstance(v, str) for v in values] )
            keep = keep and ( params[p] in values )
    return keep

def find_datasets(base_path, dataset_path, dataset_template, path_template):

    path_sep = os.path.sep
    path_params = [s.strip('{').strip('}') for s in path_template.split(path_sep)]
 
    path_depth = len(path_params)

    # file_sep = '_'

    datasets = {}

    path = os.path.join(base_path, dataset_path)
    for (dirpath, dirnames, filenames) in os.walk(path, followlinks=False):
        relpath = os.path.relpath(dirpath, base_path)
        param_values_from_path =  relpath.split(path_sep)
        params = {p:v for p,v in zip(path_params, param_values_from_path)}
        if len(param_values_from_path) == path_depth:
            dataset_id = dataset_template.format(**params)
            datasets[dataset_id] = {
                'path' : dirpath, 'params' : params
            }

    return datasets

def publication_checks(datasets, validation_file):

    filepath = validation_file
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

    # 11mar.25 
    # the following are probably obselete checks that should be removed
    # including them to see if they raise any errors
    # (they were included in publisher.py in the old publish_esgf code)
    check.append('vegtype')
    check.append('frequency')

    var_info_key = '{table_id}.{variable_id}'
    keep = set()
    not_approved = set()
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
                    not_approved.add(var_key)

            elif p == 'vegtype':
                if 'vegtype' in var_info['dimensions']:
                    raise ValueError('Can we publish this? (obselete check?)')

            elif p == 'frequency':
                table_id = var_info['CMOR table']
                ok_freqs = ['day', 'mon', 'fx', 'yr', '3hr', '6hr']
                if not any([freq in table_id for freq in ok_freqs]):
                    raise ValueError('Invalid frequency? table_id = ' + table_id)

            else:
                raise ValueError('Unknown check: ' + p)

    datasets = {s: datasets[s] for s in keep}
    print(f'Retained {len(datasets)} datasets after these validation checks: ')
    for p in check:
        print('  ' + p)
    if len(not_approved) > 0:
        print(f'Discarded {len(not_approved)} variables because no Stamp of Approval:')
        for var_key in sorted(not_approved, key=str.lower):
            print('  ' + var_key)

    return datasets
