#!/usr/bin/env python3

import argparse
import json

from collections import OrderedDict, defaultdict
from pathlib import Path
from tabulate import tabulate
from textwrap import dedent

from esgwrapper import CONFIG_FILES_DIR
from esgwrapper.utils.esgfsearch import file_size_str, show_params
from esgwrapper.utils.tools import (load_config_file, init_filter, match_params,
                                    cmip7_compound_name_without_realm)


def parse_args():

    parser = argparse.ArgumentParser(
        description='Summarize datasets according to user-specified groupings'
        )

    parser.add_argument('input', type=str,
                        help='file listing datasets, json (keyed by dataset_id) or txt (dataset_id list)')

    parser.add_argument('-c', '--config', type=str, default='groups.yaml',
                        help='yaml file specifying the metadata attributes to group by, filters, and tables; if not found, default file will be created: %(default)s')
    parser.add_argument('-vars', '--variables', type=str,
                        help='for -d, json file listing compound names of variables to keep' +
                        ' (applied before all other filtering options)')
    parser.add_argument('-core', '--BCVs', action='store_true', default=False,
                        help='shorthand for applying the -vars option with the list of BCVs' +
                        ' (Baseline Climate Variables, the Core priority variables of the CMIP7 DR)')

    return parser.parse_args()


def file_size_str_for_table(data):
    '''
    If size is zero, show "-" instead of "0 B" because it makes the table easier to read.
    '''
    if data == 0:
        return '-'
    else:
        return file_size_str(data)


def main():
    args = parse_args()

    config_file = Path(args.config)
    if not config_file.exists():
        # Copy a default config file into the current dir
        default_config_file = CONFIG_FILES_DIR / 'groupby' / 'groups.yaml'
        config_file.write_text(default_config_file.read_text())
        print(f'Wrote default config file: {config_file}')

    # Load config file specifying the dataset groupings, filters, and tables.
    config = load_config_file(args.config)
    # print(config)

    # Load file specifying dataset id's and dataset metadata attributes.
    filepath = Path(args.input)
    if filepath.suffix == '.json':
        with open(filepath, 'r') as f:
            datasets = json.load(f)['datasets']
            print(f'Loaded {filepath}')
    elif filepath.suffix == '.txt':
        raise ValueError('TODO: support .txt input')
        # convert txt file listing dataset_id's into attr:value dict for each dataset (like json input above)

    SHOW_DATASETS_SUMMARY = True
    if SHOW_DATASETS_SUMMARY:
        n = len(datasets)
        vol = sum([datasets[s]['size (bytes)'] for s in datasets])
        print(f'Number of datasets: {n}')
        print(f'Total volume: {file_size_str(vol)} ({vol} bytes)')

    # Restrict to a specified list of variables, if desired
    variables_file = args.variables
    if args.BCVs:
        # Shorthand for using the CMIP7 BCVs variables list in the config.
        # If user passed a filename via args.variables, this overrides it.
        variables_file = CONFIG_FILES_DIR / 'variables_info' / 'BCVs.json'
    if variables_file:
        with open(variables_file) as f:
            var_names = json.load(f)['Compound Name']
        # "realm" is not available from the inventory.
        # It's not required as part of the unique variable name in CMIP7, so prune it.
        var_names_no_realm = [s.partition('.')[-1] for s in var_names]
        # Confirm that this doesn't violate the uniqueness assumption
        assert len(set(var_names_no_realm)) == len(set(var_names))
        keep_var_names = var_names_no_realm
        keep_datasets = set()
        keep_variables = set()
        exclude_variables = set()
        for dataset_id, info in datasets.items():
            var_name = cmip7_compound_name_without_realm(info['params'])
            if var_name in keep_var_names:
                keep_datasets.add(dataset_id)
                keep_variables.add(var_name)
            else:
                exclude_variables.add(var_name)
        n = len(datasets)
        datasets = {s: datasets[s] for s in keep_datasets}
        print(f'Retaining only variables listed in {variables_file}')
        print(f'  --> excluded {len(exclude_variables)} variable ({n-len(datasets)} datasets)')
        print(f'  --> kept {len(keep_variables)} variables ({len(datasets)} datasets)')

    # Filter datasets.
    config = {'keep':{}, 'exclude':{}} | config
    if config['keep']:
        init_filter(config['keep'])
        print('Keeping datasets with these parameter values:')
        show_params(config['keep'], indent='  ')
        keep = set()
        for dataset_id, info in datasets.items():
            matches = match_params(info['params'], config['keep'])
            if all(matches.values()):
                keep.add(dataset_id)
        n = len(datasets)
        datasets = {s: datasets[s] for s in keep}
        print(f'  --> excluded {n-len(datasets)} datasets')
    if config['exclude']:
        init_filter(config['exclude'])
        print('Excluding datasets with these parameter values:')
        show_params(config['exclude'], indent='  ')
        exclude = set()
        for dataset_id, info in datasets.items():
            matches = match_params(info['params'], config['exclude'])
            if any(matches.values()):
                exclude.add(dataset_id)
        n = len(datasets)
        datasets = {s: datasets[s] for s in datasets if s not in exclude}
        print(f'  --> excluded {n-len(datasets)} datasets')

    # Determine the list of dataset id's that belong to each grouping.
    dataset_groups = {}
    for name, attrs in config['groupings'].items():
        # print()
        # print(name, attrs)
        group_id_template = '.'.join(['{' + attr + '}' for attr in attrs])
        # print(group_id_template)
        dataset_groups[name] = defaultdict(set)
        for dataset_id, info in datasets.items():
            group_id = group_id_template.format(**info['params'])
            # print(group_id)
            dataset_groups[name][group_id].add(dataset_id)
        # Sort group names
        dataset_groups[name] = OrderedDict({
            group_id: dataset_groups[name][group_id] for group_id in sorted(dataset_groups[name])
        })

    SHOW_GROUP_SUMMARIES = False
    if SHOW_GROUP_SUMMARIES:
        for name, groups in dataset_groups.items():
            print(f'{name}: {len(groups)} groups, no. datasets per group:')
            for group_id, dataset_ids in groups.items():
                print(f'  {group_id}: {len(dataset_ids)}')


    # TODO: save groups to output files? (useful?)



    # Make tables
    for table in config['tables']:
        # Find the intersections of dataset grouping that comprise the table entries.
        # This generates the list of dataset_id's the belong to each entry.        
        row_groups = dataset_groups[table['row']]
        col_groups = dataset_groups[table['column']]
        table_dataset_ids = {}
        for row_group_id in row_groups:
            for col_group_id in col_groups:
                key = (row_group_id, col_group_id)
                assert key not in table_dataset_ids
                table_dataset_ids[key] = row_groups[row_group_id].intersection(col_groups[col_group_id])

        col_headers = list(col_groups.keys())
        row_headers = list(row_groups.keys())
        for table_type in table['show']:
            # Get data for this table
            table_data = {}
            for row_group_id in row_headers:
                for col_group_id in col_headers:
                    key = (row_group_id, col_group_id)
                    dataset_ids = table_dataset_ids[key]
                    if table_type == 'datasets':
                        data = len(dataset_ids)
                    elif table_type == 'volume':
                        data = sum([datasets[s]['size (bytes)'] for s in dataset_ids])

                    # TODO: add more options for table type
                    #   - ensemble: ensemble size, i.e. no. of variant_label's for each model+expt
                    #   - % volume: as volume, but show as percent of total (total over full table, i.e. rows + columns)

                    else:
                        raise ValueError(f'Unknown table type: {table_type}')
                    table_data[key] = data

            # Diplay the table
            headers = [''] + col_headers + ['TOTAL:']
            rows = []
            col_sum = [0]*len(col_headers)
            for row_group_id in row_headers:
                row = [row_group_id]
                row_sum = 0
                for k, col_group_id in enumerate(col_headers):
                    data = table_data[(row_group_id, col_group_id)]
                    row_sum += data
                    col_sum[k] += data
                    if table_type == 'volume':
                        data = file_size_str_for_table(data)  # convert number of bytes to human-readable string
                    row.append(data)
                if table_type == 'volume':
                    row_sum = file_size_str_for_table(row_sum)
                row.append(row_sum)
                rows.append(row)
            total_sum = sum(col_sum)  # sum over all rows and columns, i.e. all data in the table
            col_sum.append(total_sum)
            if table_type == 'volume':
                col_sum = [file_size_str_for_table(m) for m in col_sum]
            col_sum = ['TOTAL:'] + col_sum
            rows.append(col_sum)
            # Replace zeros with "-" for easier reading of the table
            for row in rows:
                for k, col in enumerate(row):
                    if isinstance(col, int) and col == 0:
                        row[k] = '-'
            # Print table to stdout
            print(f'\nTable: {table_type}, Axes: {table["row"]} vs {table["column"]}')
            print(tabulate(rows, headers=headers))

        # TODO: add csv output option


if __name__ == '__main__':
    main()
