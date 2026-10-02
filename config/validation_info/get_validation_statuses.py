#!/usr/bin/env python
'''
Get validation status of variables from A4D validation system database.

Based on instructions here, developed from code from Kristi Webb:
    https://gitlab.science.gc.ca/CCCma/CCCma_tools/-/blob/develop_canesm/data_conv/ncconv/projects/CMIP7/README_validation_info.md
as well as Russell Dietrich's script:
    https://gitlab.science.gc.ca/rrd001/canesm_integration_testing/-/blob/main/check_a4d_valid_status_cmip7.sh

Sourcing postgresql_export.sh gives access to psql. 
If for some reason this doesn't work, an env with psql can be created and used:
    conda env create --name env_validation_db -f env_validation_db.yml
    conda activate env_validation_db
'''

import argparse
import csv
import json
import os
import subprocess

from collections import OrderedDict
from datetime import datetime, UTC

def parse_args():
    parser = argparse.ArgumentParser(
        description='Get validation statuses of variables from A4D database and write variable statuses to json file'
    )

    parser.add_argument('-ndb', '--no-database', action='store_true',
                        help='do not get csv files from validation databases, \
                             instead use csv files that already exist in the current directory')

    return parser.parse_args()

def get_database_files():
    # Get csv files from validation database
    print('Fetching variable statuses from A4D validation database')
    cwd = os.getcwd()
    command = f'''\
    ssh hpcr7-vis6 << EOF
    cd {cwd}
    source postgresql_export.sh
    ./download_validation_files.sh
    EOF
    '''
    result = subprocess.run(
        command,
        shell=True,
        check=True,
        text=True,
        capture_output=True
    )

def parse_cmip7_compound_name(var_name: str) -> dict:
    '''
    Return dict of attribute:value pairs for the attributes in the compound name.
    Example CMIP7 compound name from the CMIP7 Data Request: "seaIce.sieqthick.tavg-u-hxy-si.mon.glb"
    '''
    sep = '.'
    assert var_name.count(sep) == 4
    attrs = ('realm', 'variable_id', 'branding_suffix', 'frequency', 'region')
    vals = var_name.split(sep)
    return dict(zip(attrs,vals))

def main():
    args = parse_args()

    if not args.no_database:
        get_database_files()

    models = ['CanESM5-1', 'CanESM6-0-MR']

    date_run = datetime.now(UTC)
    time_fmt = '%d %b %Y %H:%M:%S UTC'
    date_run_str = date_run.strftime(time_fmt)

    variable_status = OrderedDict()
    model_info = OrderedDict()
    for model in sorted(models, key=str.lower):
        filename = f'variable_status_CMIP7_{model}.csv'
        print(f'Loading variable validation statuses for {model} from {filename}')
        file_mod_time = datetime.fromtimestamp(os.stat(filename).st_mtime, tz=UTC)

        csv_reader = None
        var_list = []
        with open(filename) as f:
            csv_reader = csv.reader(f)
            columns = next(csv_reader)
            ncol = len(columns)
            for row in csv_reader:
                assert len(row) == ncol
                var_info = {col:val for col,val in zip(columns,row)}                
                var_list.append(var_info)

        var_status = {}
        order = ('aggregate_status', 'source_id', 'cmip7_compound_name',
                 'realm', 'variable_id', 'branding_suffix', 'frequency', 'region',
                 'uid')
        for var_info in var_list:
            var_name = var_info['cmip7_compound_name']
            var_info.update(parse_cmip7_compound_name(var_name))
            var_info['source_id'] = model
            assert var_name not in var_status, f'Status was already defined for {model} {var_name}'
            var_status[var_name] = OrderedDict({key: var_info[key] for key in order})

        var_names = sorted(var_status, key=str.lower)
        variable_status[model] = OrderedDict({var_name: var_status[var_name] for var_name in var_names})

        all_statuses = set([var_info['aggregate_status'] for var_info in var_status.values()])
        vars_by_status = OrderedDict()
        for status in sorted(all_statuses, key=str.lower):
            vars_by_status[status] = len([var_info for var_info in var_status.values()
                                          if var_info['aggregate_status'] == status])
        
        model_info[model] = OrderedDict({
            'provenance file': filename,
            'provenance file timestamp': file_mod_time.strftime(time_fmt),
            'no. of variables': len(var_names),
            'no. of variables by status': vars_by_status,
        })
        del var_names, var_status

    out = OrderedDict({
        'Header': OrderedDict({
            'date run': date_run_str,
            'models': model_info,
        }),
        'model': variable_status
    })
    outfile = 'validation_status.json'
    with open(outfile, 'w') as f:
        json.dump(out, f, indent=4)
        print(f'Wrote {outfile}')

if __name__ == '__main__':
    main()
