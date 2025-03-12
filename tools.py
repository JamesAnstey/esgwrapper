#!/usr/bin/env python

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






