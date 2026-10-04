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

# See get_database_files() for what CSV_VERSION means
CSV_VERSION = 2

def parse_args():
    parser = argparse.ArgumentParser(
        description='Get validation statuses of variables from A4D database and write variable statuses to json file'
    )

    parser.add_argument('-ndb', '--no-database', action='store_true',
                        help='do not get csv files from validation databases, \
                             instead use csv files that already exist in the current directory')

    return parser.parse_args()

def get_database_files(csv_version: int = 2):
    '''
    Get csv files from validation database.

    csv_method = 1 produces a csv file with these columns:
        uid,cmip7_compound_name,aggregate_status
        8b97fe6e-4a5b-11e6-9cd2-ac72891c3257,atmos.utendwtem.tavg-p39-hy-air.day.glb,approved
        71291d86-faa7-11e6-bfb7-ac72891c3257,seaIce.sieqthick.tavg-u-hxy-si.mon.glb,approved
        ...
    csv_method = 2 produces a csv file with these columns:
        uid,aggregate_status,cmip7_compound_name,source_run,diagnostic_config_hash,source_filepath,CMOR_output_version
        83bbfc68-7f07-11ef-9308-b1dd71e64bec,approved,ocean.friver.tavg-u-hxy-sea.3hr.glb,v51-c7-jl31-hist-p,32193eff0cf7c5c3604471e2429958d6ebaaec09079ae2a931db82aeb2e83a17,/home/rrd001/site7/canesm_runs/v51-c7-jl31-hist-p/data/nc_output/MIP-DRS7/CMIP7/CMIP/CCCma/CanESM5-1/historical/r1i1p2f1/glb/3hr/friver/tavg-u-hxy-sea/g127/v20260723/friver_tavg-u-hxy-sea_3hr_glb_g127_CanESM5-1_historical_r1i1p2f1_185001010130-185012312230.nc,v20260723
        19bebf2a-81b1-11e6-92de-ac72891c3257,approved,aerosol.abs550aer.tavg-u-hxy-u.mon.glb,v51-c7-jl31-hist-p,0a73879c41ee960653d2c5d59233a76adef3269dbfa73940e1135e7120194d22,/home/rrd001/site7/canesm_runs/v51-c7-jl31-hist-p/data/nc_output/MIP-DRS7/CMIP7/CMIP/CCCma/CanESM5-1/historical/r1i1p2f1/glb/mon/abs550aer/tavg-u-hxy-u/g120/v20190429/abs550aer_tavg-u-hxy-u_mon_glb_g120_CanESM5-1_historical_r1i1p2f1_185001-185012.nc,v20190429
        ...
    '''
    print('Fetching variable statuses from A4D validation database')
    cwd = os.getcwd()
    if csv_version == 1:
        cmds = [
            f'cd {cwd}',
            'source postgresql_export.sh',
            './download_validation_files.sh'
        ]
    elif csv_version == 2:
        cmds = [
            f'cd {cwd}',
            'source /fs/homeu3/eccc/crd/ords/cccma/rja001/venv/esgwrapper/bin/activate',
            'python download_database_table.py --database_name CMIP7_CanESM5.1',
            'python download_database_table.py --database_name CMIP7_CanESM6.0'
        ]
    else:
        raise ValueError('what kind of csv file to get from database?')

    ssh_cmd = [
        'ssh', 'hpcr7-vis6',
        ' && '.join(cmds)
    ]

    try:
        result = subprocess.run(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e.stderr}")
        return None


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
        get_database_files(CSV_VERSION)

    models = ['CanESM5-1', 'CanESM6-0-MR']

    date_run = datetime.now(UTC)
    time_fmt = '%d %b %Y %H:%M:%S UTC'
    date_run_str = date_run.strftime(time_fmt)

    variable_status = OrderedDict()
    model_info = OrderedDict()
    check_columns_of_duplicates = ['uid', 'aggregate_status', 'cmip7_compound_name']
    for model in sorted(models, key=str.lower):
        if CSV_VERSION == 1:
            filename = f'variable_status_CMIP7_{model}.csv'
        elif CSV_VERSION == 2:
            filename = f'variable_status_CMIP7_{model}_v2.csv'
        else:
            raise ValueError(CSV_VERSION)
        print(f'Loading variable validation statuses for {model} from {filename}')
        file_mod_time = datetime.fromtimestamp(os.stat(filename).st_mtime, tz=UTC)

        csv_reader, columns = None, None
        var_list = []
        with open(filename) as f:
            csv_reader = csv.reader(f)
            columns = next(csv_reader)
            ncol = len(columns)
            for row in csv_reader:
                assert len(row) == ncol
                var_info = {col:val for col,val in zip(columns,row)}
                var_list.append(var_info)

        rekey = {
            'CMOR_output_version': 'version'
        }
        for var_info in var_list:
            for old,new in rekey.items():
                if old in var_info:
                    var_info[new] = var_info[old]
                    var_info.pop(old)
            if 'version' not in var_info:
                # CSV_VERSION = 1 does not include the dataset version, CSV_VERSION = 2
                assert CSV_VERSION == 1
                var_info['version'] = ''

        # Set metadata parameters and create dict keyed by variable name for this model
        var_status = {}
        for var_info in var_list:
            var_name = var_info['cmip7_compound_name']
            var_info.update(parse_cmip7_compound_name(var_name))
            var_info['source_id'] = model

            # assert var_name not in var_status, f'Status was already defined for {model} {var_name}'
            if var_name not in var_status:
               var_status[var_name] = var_info
            else:
                # For CSV_VERSION=2, a variable can appear more than once in the csv file.
                # Check that its essential parameters agree with the previous entry.
                var_info_existing = var_status[var_name]
                assert all([var_info[c] == var_info_existing[c] for c in check_columns_of_duplicates]), \
                           f'Unexpected column differences for {var_name}'
        del var_list

        # Retain only desired variable info
        order = ('aggregate_status', 'version', 'source_id', 'cmip7_compound_name',
                 'realm', 'variable_id', 'branding_suffix', 'frequency', 'region',
                 'uid')
        for var_name, var_info in var_status.items():
            var_status[var_name] = OrderedDict({key: var_info[key] for key in order})

        var_names = sorted(var_status, key=str.lower)
        variable_status[model] = OrderedDict({var_name: var_status[var_name] for var_name in var_names})

        # Count variables by status
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
