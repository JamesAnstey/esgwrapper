#!/usr/bin/env python

import json
import logging
import numpy as np
import os
import stat
import sys
import yaml

from collections import OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path

import esgvoc.api as ev
from esgvoc.apps.drs.validator import DrsValidator

from esgwrapper.utils.esgfsearch import file_size_str

logger = logging.getLogger(__name__)


TIME_STR_FORMAT_BY_LENGTH = {
    4: '%Y', # example: '2022'
    6: '%Y%m', # example: '185001'
    8: '%Y%m%d', # example: '18500101'
    12: '%Y%m%d%H%M', # example: '202201010300'
}


class TeeStdoutToLogger:
    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        self.terminal = sys.__stdout__  # Keep track of original stdout
    def write(self, message):
        # Avoid logging empty lines or pure whitespace from print endings
        if message.strip():
            # self.logger.log(self.level, message.strip())
            self.logger.log(self.level, message)
        self.terminal.write(message)  # Pass through to original console
    def flush(self):
        self.terminal.flush()  # Keep buffering behave correctly


def load_config_file(config_file: str | Path) -> dict:
    '''
    Load yaml configuration file and return contents as dict.
    '''
    if not os.path.exists(config_file):
        raise OSError('Config file not found: ' + config_file)
    with open(config_file) as f:
        config = yaml.safe_load(f)
        print('Loaded ' + str(config_file))
    return config


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


def _validate_dir_permissions(dirpath):
    file_stat = os.stat(dirpath)
    mode = file_stat.st_mode
    check = []
    check.append(bool(mode & stat.S_IRUSR))  # owner can read
    check.append(bool(mode & stat.S_IRGRP))  # group can read
    check.append(bool(mode & stat.S_IROTH))  # whole world can read
    return all(check)


def _validate_dataset_path(path: str, params: dict, path_template: str,
                           validator: DrsValidator = None,
                           ) -> bool:
    '''
    Check that directory path is valid for a dataset.
    Input variable "path" is eexpected to be only the dataset path, it should
    not contain other leading path components.
    '''
    check = []
    path = os.path.normpath(path)

    # Check directory path structure follows the DRS by substituing its parameter values 
    # (which are passed to the function in the "params" dict) into the path template and
    # comparing that to the actual path.
    dataset_path = path_template.format(**params)
    check.append(path == dataset_path)

    if validator:
        # Check dataset path using the esgvoc filename validator. This checks against the
        # official project CVs. Note, esgvoc's validate_directory function does not
        # automatically strip leading path elements, so it's necessary to pass it
        # dataset_path, rather than the full path.
        # validation_report = validator.validate_directory(dataset_path)
        validation_report = validator.validate_directory(path)
        check.append(validation_report.validated)

    return all(check)


def _validate_dataset_filename(project: str,
                               filename: str, params: dict, file_template: str,
                               validator: DrsValidator = None,
                               ) -> bool:
    '''
    Check that filename is valid for a dataset.
    '''
    check = []

    file_template_noext, valid_ext = os.path.splitext(file_template)
    filename_noext, ext = os.path.splitext(filename)

    # Check filename extension
    check.append(ext == valid_ext)

    # Check filename doesn't start with '.', which could indicate a file being rsync'd
    # (i.e., the rsync is still in progress)
    check.append(not filename.startswith('.'))

    # Check filename follows the DRS by substituing its parameter values (which are passed
    # to the function in the "params" dict) into the filename template and comparing that
    # to the actual filename.
    if project == 'cmip7':
        assert file_template_noext.endswith('_{timeRangeDD}'), \
            f'Unexpected file_template for {project}: {file_template}'
        file_template_notime = file_template_noext.rpartition('_')[0]
        if params['frequency'] == 'fx':
            filename_notime = filename_noext
        else:
            filename_notime = filename_noext.rpartition('_')[0]
    else:
        raise ValueError(f'Where in the filename is the time string for {project}? Received: {file_template}')
    check.append(filename_notime == file_template_notime.format(**params))

    if validator:
        # Check filename using the esgvoc filename validator. This checks against the official project CVs.
        # (Hence it should be sufficient on its own, but since I added this after already implementing the
        # checks above I'll leave both those and the esgvoc check in here for now.)
        # Note: validation_report.errors lists any errors found, validation_report.warnings lists warnings
        validation_report = validator.validate_file_name(filename)
        check.append(validation_report.validated)

    return all(check)


def _parse_time_str(s: str) -> datetime:
    n = len(s)
    if n not in TIME_STR_FORMAT_BY_LENGTH:
        raise ValueError(f'Unexpected time string {s} of length={n}, how should it be parsed?')
    return datetime.strptime(s, TIME_STR_FORMAT_BY_LENGTH[n])


def _validate_year_ranges(year_ranges: np.array) -> bool:
    '''
    Check that dataset years are contiguous, based on the start/stop times.

    year_ranges is an array like the time_bnds in a netcdf file, for example:
        array([[6500., 6600.],
               [6601., 6700.],
               [6701., 6800.]])
    In the above example each file starts with a new calendar year. But we also
    allow for this case:
        array([[1850., 1861.],
               [1861., 1871.],
               [1871., 1881.]])
    where the end year of a file is the same as the start year of the next one.
    The reason is that some datasets have files like:
        vas_tpt-h10m-hxy-u_6hr_glb_g120_CanESM5-1_1pctCO2_r1i1p2f1_185001010600-186101010000.nc
        vas_tpt-h10m-hxy-u_6hr_glb_g120_CanESM5-1_1pctCO2_r1i1p2f1_186101010600-187101010000.nc
        vas_tpt-h10m-hxy-u_6hr_glb_g120_CanESM5-1_1pctCO2_r1i1p2f1_187101010600-188101010000.nc
    where the last time of a file is the first time of the next calendar year.
    '''
    # Check that consecutive files' start & stop times are at least 1 year apart.
    assert np.all(np.diff(year_ranges, axis=0)) > 0, \
        f'Unexpected order of start/stop file times: {year_ranges}'
    # Check that within each time range the start time is the same year or later than the stop time.
    assert np.all(np.diff(year_ranges, axis=1)) >= 0, \
        f'Unexpected time range within file times: {year_ranges}'
    # Check that each stop time is not more than a year before the next start time.
    year_gaps = year_ranges[1:,0] - year_ranges[:-1,1]
    assert bool(np.all(year_gaps >= 0)), \
        f'Found negative year gaps in file times: {year_ranges}'
    return bool(np.all(year_gaps <= 1))


def _get_file_times(project: str, dataset_files: list[str]) -> np.array:
    year_ranges = np.zeros((len(dataset_files),2))
    year_ranges.fill(np.nan)
    if project == 'cmip7':
        # dataset_files is assumed to be sorted from earliest to latest times
        for k,filename in enumerate(dataset_files):
            filename, ext = os.path.splitext(filename)
            time_range_str = filename.split('_')[-1]
            assert time_range_str.count('-') == 1, f'Unexpected time range in filename: {time_range_str}'
            time_str_start, time_str_stop = time_range_str.split('-')
            time_start = _parse_time_str(time_str_start)
            time_stop = _parse_time_str(time_str_stop)
            year_ranges[k,0] = time_start.year
            year_ranges[k,1] = time_stop.year
    else:
        raise ValueError(f'How to get file times for {project}?')
    assert not np.any(year_ranges == np.nan), f'Failed to find some file time ranges: {year_ranges}'
    return year_ranges


def _check_dataset_years(project: str, dataset_files: list[str], params: dict) -> dict:
    '''
    Validate the years indicated by a dataset's filenames span the expected range of
    years, or minimum number of years, for the experiment.

    Only years are checked. Any months, days, etc in the filename's time string are ignored.
    Only the filename is used. The file contents are not accessed to verify that the time string
    accurately represents the times in the file (CMOR and the QC checker should handle that).
    '''
    check = {}
    if len(dataset_files) == 0:
        return False
    if project == 'cmip7':
        if params['frequency'] == 'fx':
            # For fixed fields (with no time dimension), this check is irrelevant
            return True
        else:
            year_ranges = _get_file_times(project, dataset_files)
            if not _validate_year_ranges(year_ranges):
                # Failure here indicates the dataset years are not contiguous, i.e. there are time gaps.
                logger.info(f' dataset has year gaps')
                return False

            # Get info from CVs about time range of the experiment
            expt = params['experiment_id']
            cv_info = ev.get_term_in_collection(project_id=project, collection_id='experiment', term_id=expt.lower())
            assert expt == cv_info.drs_name, f'Unexpected DRS name for experiment {expt}: {cv_info.drs_name}'

            dataset_start_year = year_ranges[0,0]
            dataset_end_year = year_ranges[-1,-1]
            dataset_total_years = dataset_end_year - dataset_start_year + 1
            check = []
            if cv_info.start_timestamp:
                # Check that dataset begins in the start year specified in the CVs.
                dt_start = cv_info.start_timestamp
                check.append(dataset_start_year == dt_start.year)
                if not check[-1]:
                    logger.info(f' dataset starts in year {dataset_start_year}, '
                                f'but should start in year={dt_start.year}')
            if cv_info.end_timestamp:
                # Check that dataset ends in the end year specified in the CVs, or ends in the
                # year following that.
                #
                # The second case is allowed because times in a file possibly can include the 
                # first time of the calendar year following the end year of an experiment, for example:
                #   vas_tpt-h10m-hxy-u_3hr_glb_g150_CanESM6-0-MR_historical_r12i1p1f1_202101010300-202201010000.nc
                # where the CMIP7 historical experiment ends at the end of 2021.
                dt_end = cv_info.end_timestamp
                check.append(dataset_end_year == dt_end.year or dataset_end_year == dt_end.year + 1)
                if not check[-1]:
                    logger.info(f' dataset ends in year {dataset_end_year}, '
                                f'but should end in year={dt_end.year}')
            if cv_info.min_number_yrs_per_sim:
                check.append(dataset_total_years >= cv_info.min_number_yrs_per_sim)
                if not check[-1]:
                    logger.info(f' dataset has {dataset_total_years} years, '
                                f'minimum number of years={cv_info.min_number_yrs_per_sim}')
            if len(check) == 0:
                raise ValueError(f'No dataset time range checks were applied, is the needed info in the CVs?')
            return all(check)
    else:
        raise ValueError(f'How to check experiment years for {project}?')


def find_datasets(project: str,
                  base_path: str,
                  dataset_path: str,
                  dataset_template: str,
                  path_template: str,
                  file_template: str,
                  ) -> dict:
    '''
    Walk directory to find datasets and gather info about them.
    '''

    path_sep = os.path.sep
    path_params = [s.strip('{').strip('}') for s in path_template.split(path_sep)]
 
    path_depth = len(path_params)

    datasets = {}

    use_esgvoc_validator = False
    if use_esgvoc_validator:
        # To use esgvoc DRS validation (checking file and dir names), pass this validator
        # object to the checking functions.
        validator = DrsValidator(project_id=project)
    else:
        # To not use the esgvoc validator, set validator=None. Using it can slow down the
        # inventory significantly, and there are still some checks in place when it's not used.        
        validator = None

    check_dir_permissions = True

    path = os.path.join(base_path, dataset_path)
    for (dirpath, dirnames, filenames) in os.walk(path, followlinks=False):
        # print(dirpath, dirnames, filenames)
        if check_dir_permissions:
            if not _validate_dir_permissions(dirpath):
                # If permissions are invalid, reject this path and ignore all dirs under it
                logger.info(f' * REJECTED * wrong permissions: {dirpath}')
                dirnames[:] = []
                continue
        relpath = os.path.relpath(dirpath, base_path)
        param_values_from_path =  relpath.split(path_sep)
        params = {p:v for p,v in zip(path_params, param_values_from_path)}
        if len(param_values_from_path) == path_depth:
            # Validate dataset path
            if not _validate_dataset_path(relpath, params, path_template, validator):
                logger.info(f' * REJECTED * invalid path: {relpath}')
                continue
            reject_dataset = False
            dataset_id = dataset_template.format(**params)
            logger.info(f' Found dataset: {dataset_id}')
            logger.info(f' path: {dirpath}')
            dataset_files = set()
            invalid_files = set()
            for filename in filenames:
                if _validate_dataset_filename(project, filename, params, file_template, validator):
                    dataset_files.add(filename)
                else:
                    invalid_files.add(filename)

            dataset_files = sorted(dataset_files, key=str.lower)
            if len(invalid_files) > 0:
                # If any invalid files were found in the dataset dir, reject it
                logger.info(f' invalid files were found in dataset dir')
                reject_dataset = True
            if len(dataset_files) == 0:
                logger.info(f' no valid dataset files were found')
                reject_dataset = True
            if not _check_dataset_years(project, dataset_files, params):
                # If dataset does not contain all expected years, reject it
                logger.info(f' failed time range checks (see above for why)')
                reject_dataset = True

            if reject_dataset:
                logger.info(f' * REJECTED * {dataset_id}')
            else:
                logger.info(f' * ACCEPTED * {dataset_id}')
                datasets[dataset_id] = {
                    'path' : dirpath, 'params' : params
                }
                datasets[dataset_id].update({
                    'no. of files' : len(dataset_files), 'filenames' : dataset_files,
                })
                size = 0
                for filename in dataset_files:
                    size += os.stat(os.path.join(dirpath, filename)).st_size
                datasets[dataset_id].update({
                    'size (bytes)' : size, 'size (human readable)' : file_size_str(size)
                })

    return datasets


def get_unique_param_values(datasets, dataset_parameters):
    param_unique_values = OrderedDict()
    for p in dataset_parameters:
        param_unique_values[p] = sorted(set([d['params'][p] for d in datasets.values()]), key=str.lower)
    return param_unique_values


def cmip7_compound_name(params):
   '''
   Return CMIP7 compound name as defined in the CMIP7 Data Request.
   This name uniquely identifies a requested variable (i.e., a CMOR variable).
   '''
   template = '{realm}.{variable_id}.{branding_suffix}.{frequency}.{region}'
   return template.format(**params)


def cmip7_compound_name_without_realm(params):
   '''
   Return CMIP7 compound name as defined in the CMIP7 Data Request, but excluding the realm.
   This name should uniquely identifies a requested variable (i.e., a CMOR variable) since the realm
   is not required for uniqueness.
   '''
   template = '{variable_id}.{branding_suffix}.{frequency}.{region}'
   return template.format(**params)


def check_a4d_validation_status(datasets, validation_file):
    '''
    Check validation status of variables before publishing.
    Uses validation info from A4D validation database.
    '''
    with open(validation_file) as f:
        variable_status = json.load(f)['model']

    # "realm" is not available from the inventory.
    # It's not required as part of the unique variable name in CMIP7, so prune it.
    # Confirm that this doesn't violate the uniqueness assumption.
    variable_status2 = {model: {} for model in variable_status}
    for model, vars in variable_status.items():
        for var_name, var_info in vars.items():
            var_name2 = cmip7_compound_name_without_realm(var_info)
            assert var_name.endswith(var_name2)  # double check!
            assert var_name2 not in variable_status2[model]  # confirm doesn't violate uniqueness
            variable_status2[model][var_name2] = var_info
    # Check variable name uniqueness once more... just to be extra sure
    for model in variable_status:
        assert len(set(variable_status[model].keys())) == len(set(variable_status2[model].keys()))
    variable_status = variable_status2
    del variable_status2

    # Go through datasets and exclude any that are not approved or have incorrect version.
    # Log any rejections.
    exclude_datasets = []
    exclude_variables = set()
    for dataset_id, info in datasets.items():
        var_name = cmip7_compound_name_without_realm(info['params'])
        model = info['params']['source_id']
        var_info = variable_status[model][var_name]  # if variable is published, it must have an entry
        if var_info['aggregate_status'] != 'approved':
            logger.info(f' {var_name} not approved for {model}, discarding dataset: {dataset_id}')
            exclude_datasets.append(dataset_id)
            exclude_variables.add(cmip7_compound_name(var_info))
        dataset_version = info['params']['version']  # dataset version found in the inventory
        if var_info['version'] != dataset_version:
            assert var_info['version'] != '', 'Was CSV_VERSION=2 used in get_validation_statuses.py?'
            logger.info(f' {var_name} incorrect version {dataset_version} for {model}, discarding dataset: {dataset_id}')
            exclude_datasets.append(dataset_id)
            exclude_variables.add(cmip7_compound_name(var_info))
    for dataset_id in exclude_datasets:
        datasets.pop(dataset_id)
    if len(exclude_variables) == 0:
        msg = f'All variables are approved'
        print(f'{msg}')
        logger.info(f' * VALIDATION SUCCESS * {msg}')
    else:
        msg = f'{len(exclude_variables)} unapproved variables from {len(exclude_datasets)} datasets were excluded'
        print(f'WARNING: {msg}')
        logger.info(f' * VALIDATION FAILURE * {msg}')


def publication_checks(datasets, validation_file):
    '''
    Check CMIP6 Stamp of Approval. Superseded for CMIP7 by check_a4d_validation_status().
    '''
    raise Exception('deprecated')

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
        print(f'Retained {len(datasets)} datasets after filtering by data request ' +
              f'(excluded {n-len(datasets)} datasets that were not requested)')

    else:
        raise ValueError(f'Need to specify how to filter variables based {project} data request')

    return datasets
