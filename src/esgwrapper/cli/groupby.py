#!/usr/bin/env python3

import argparse
import json

from collections import OrderedDict, defaultdict
from pathlib import Path
from tabulate import tabulate

from esgwrapper.utils.esgfsearch import file_size_str
from esgwrapper.utils.tools import load_config_file


def parse_args():

    parser = argparse.ArgumentParser(
        description='Summarize datasets according to user-specified groupings'
        )

    parser.add_argument('input', type=str,
                        help='file listing datasets, json (keyed by dataset_id) or txt (dataset_id list)')
    parser.add_argument('config', type=str,
                        help='yaml file specifying the metadata attributes to group by, filters, and tables')
    
    return parser.parse_args()


def main():
    args = parse_args()

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

    # TODO: if input is STAC search, convert map attr names, activate w/ '-stac' option

    SHOW_DATASETS_SUMMARY = True
    if SHOW_DATASETS_SUMMARY:
        n = len(datasets)
        vol = sum([datasets[s]['size (bytes)'] for s in datasets])
        print(f'Number of datasets: {n}')
        print(f'Total volume: {file_size_str(vol)} ({vol} bytes)')

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
                        data = file_size_str(data)  # convert number of bytes to human-readable string
                    row.append(data)
                if table_type == 'volume':
                    row_sum = file_size_str(row_sum)
                row.append(row_sum)
                rows.append(row)
            total_sum = sum(col_sum)  # sum over all rows and columns, i.e. all data in the table
            col_sum.append(total_sum)
            if table_type == 'volume':
                col_sum = [file_size_str(m) for m in col_sum]
            col_sum = ['TOTAL:'] + col_sum
            rows.append(col_sum)
            print(f'\nTable: {table_type}, Axes: {table["row"]} vs {table["column"]}')
            print(tabulate(rows, headers=headers))

        # TODO: add csv output option


if __name__ == '__main__':
    main()
