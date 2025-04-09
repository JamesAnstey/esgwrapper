#!/usr/bin/env python

import json
import os
from collections import OrderedDict, defaultdict

from esgfsearch import file_size_str


def match_params(params, reference):
    # Loop over parameters (p) in the reference, checking for matches in each of them
    matches = {}
    for p in reference:

        if p not in params:
            continue

        # Get value(s) of the reference parameter
        if isinstance(reference[p], str):
            # If only a single value (str) was passed, cast it as a list
            values = [reference[p]]
        elif isinstance(reference[p], list):
            # Already a list, so ok, but check they're all str
            values = reference[p]
            if not all( [isinstance(v, str) for v in values] ):
                raise TypeError(f'list of str is required, received: {values}')
        else:
            raise TypeError(f'wrong type for reference parameters: {type(reference[p])}')

        matches[p] = params[p] in values

    return matches


def find_datasets(base_path, dataset_path, dataset_template, path_template, get_size=False):

    path_sep = os.path.sep
    path_params = [s.strip('{').strip('}') for s in path_template.split(path_sep)]
 
    path_depth = len(path_params)

    datasets = {}

    valid_ext = ['.nc']

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
            dataset_files = set()
            for filename in filenames:
                if os.path.splitext(filename)[-1] in valid_ext:
                    dataset_files.add(filename)
            dataset_files = sorted(filenames, key=str.lower)
            datasets[dataset_id].update({
                'no. of files' : len(dataset_files), 'filenames' : dataset_files,
            })
            if get_size:
                size = 0
                for filename in dataset_files:
                    size += os.stat(os.path.join(dirpath, filename)).st_size
                datasets[dataset_id].update({
                    'size' : size, 'size_str' : file_size_str(size)
                })

    return datasets


def get_unique_param_values(datasets, dataset_parameters):
    param_unique_values = OrderedDict()
    for p in dataset_parameters:
        param_unique_values[p] = sorted(set([d['params'][p] for d in datasets.values()]), key=str.lower)
    return param_unique_values


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


def get_dreq_validation_file(project, repo_path):
    dreq_info = {
        'cmip6': 'request_vars_01.00.33.json'
    }
    if project not in dreq_info:
        raise ValueError(f'Need to specify location of data request information for {project}')
    return os.path.join(repo_path, os.path.join('input', dreq_info[project]))


def data_request_checks(datasets, validation_file, verbose=False):

    filepath = validation_file
    with open(filepath, 'r') as f:
        dreq = json.load(f)
        print('Loaded ' + filepath)

    project = dreq['info']['project']
    expt_vars = defaultdict(set)
    expt_missing_priority = defaultdict(list)
    if project == 'cmip6':
        # use all priority levels
        use_priority_levels = [str(m) for m in dreq['info']['priorities']]
        # for each experiment, get full set of requested variables
        for expt in dreq['vars']:
            vars_by_priority = dreq['vars'][expt]['vars by priority']
            for p in use_priority_levels:
                if p in vars_by_priority:
                    expt_vars[expt].update(vars_by_priority[p])
                else:
                    expt_missing_priority[expt].append(p)
            if verbose:
                print(f'{len(expt_vars[expt])} requested variables for {expt}')
        if verbose:
            print('Missing priority levels for these experiments:')
            for expt in sorted(expt_missing_priority, key=str.lower):
                print(f'  {expt}: ' + ', '.join(expt_missing_priority[expt]))
        # loop over datasets to determine which ones are requested
        var_name_template = '{table_id}.{variable_id}'
        keep = set()
        for dataset_id, info in datasets.items():
            var_name = var_name_template.format(**info['params'])
            expt = info['params']['experiment_id']
            if var_name in expt_vars[expt]:
                keep.add(dataset_id)
        n = len(datasets)
        datasets = {s: datasets[s] for s in keep}
        print(f'Retained {len(datasets)} requested datasets (excluded {n-len(datasets)} datasets that were not requested)')

    else:
        raise ValueError(f'Need to specify how to filter variables based {project} data request')

    return datasets
