#!/usr/bin/env python
'''
Set up working dir(s) for publishing.
'''

import argparse
import os
import yaml

from copy import deepcopy
from textwrap import indent

from esgwrapper import (CONFIG_FILES_DIR, DEFAULT_WORKDIRS_CONFIG_FILE, WORK_ROOT_DIR)
from esgwrapper.utils.tools import load_config_file


class work_dir(dict):
    def __init__(self,
                 project: str, inventory: dict,
                 paths: list[str],
                 keep: dict = None, exclude: dict = None,
                 **kwargs):
        self.project = project
        self.inventory = inventory
        self.keep = keep if keep else {}
        self.exclude = exclude if exclude else {}
        self.paths = paths
    def __repr__(self):
        return str(self.__dict__)
    def update(self, inventory: dict, keep: dict = None, exclude: dict = None):
        self.inventory.update(inventory)
        if keep:
            self.keep.update(keep)
        if exclude:
            self.exclude.update(exclude)
    def dir_name(self):
        dir_name = self.project
        dir_name += '_{source_id}_{experiment_id}'.format(**self.inventory)
        return dir_name

def parse_args():
    parser = argparse.ArgumentParser(
        description='Set up one or more working directories for ESGF publishing. '
    )

    parser.add_argument('-c', '--config', type=str, default=DEFAULT_WORKDIRS_CONFIG_FILE,
                        help='config file to set up working directories, default: %(default)s')
    parser.add_argument('--clobber', action='store_true',
                        help='if a work dir of the same name already exists, overwrite it')
    parser.add_argument('-np', '--no-prompt', action='store_true',
                        help='do not prompt user to confirm work dir creation')

    return parser.parse_args()

def main():
    args = parse_args()
    prompt_user = not args.no_prompt

    # Load dataset configuration settings from config file
    config_wrk = load_config_file(args.config)
    project = config_wrk['project']
    # Load publisher configuration settings from config file
    config_pub = load_config_file(CONFIG_FILES_DIR / 'config-publisher.yaml')
    path_template = config_pub['DRS'][project]['path']
    path_attrs = [s.strip('}').strip('{') for s in path_template.split('}/{')]

    # Get parameters that will be used by all work dirs unless overridden
    base_config = work_dir(**config_wrk)

    # TODO: validate parameters against CVs

    if 'separate_work_dirs' not in config_wrk:
        # Set up only one dir, using the common parameters set
        config_wrk['separate_work_dirs'] = [{}]

    # Determine parameter set for each work dir
    work_dirs = []
    for d in config_wrk['separate_work_dirs']:
        wrk = deepcopy(base_config)
        wrk.update(**d)
        work_dirs.append(wrk)

    # Create dict to write a config-dataset.yaml in the work dir
    for wrk in work_dirs:

        # Translate inventory parameters into DRS paths
        # TODO: have better solution than this depending on order of attributes in the DRS path template
        params = dict(wrk.inventory)
        path = []
        used_attrs = []
        for attr in path_attrs:
            if attr in params and len(params[attr]) > 0:
                path.append(params[attr])
                used_attrs.append(attr)
            else:
                break
        if len(used_attrs) < len(params):
            # Warn user that some parameters were ignored
            unused_attrs = [s for s in path_attrs if (s in params and s not in used_attrs)]
            print(f'* WARNING * these attributes were ignored in the inventory path: {", ".join(unused_attrs)}')
        path = os.path.normpath(os.path.sep.join(path))

        config_dat = {
            'project': wrk.project,
            'inventory': [path],
        }
        if wrk.keep:
            config_dat['keep'] = wrk.keep
        if wrk.exclude:
            config_dat['exclude'] = wrk.exclude
        config_dat['paths'] = wrk.paths

        work_dir_path = WORK_ROOT_DIR / wrk.dir_name()
        if os.path.exists(work_dir_path) and not args.clobber:
            print(f'Not overwriting existing work dir: {work_dir_path}')
            continue

        if prompt_user:
            print(f'\nWork dir path:\n  {work_dir_path}')
            print('\nconfig-dataset.yaml parameters:')
            config_dat_yaml = yaml.safe_dump(config_dat, default_flow_style=False, sort_keys=False)
            print(indent(config_dat_yaml, '  '))
            ok = input(f'Create the above work dir? (ENTER or "y" for yes, anything else for no): ')
        else:
            ok = ''
        if ok in ['', 'y']:
            if not os.path.exists(work_dir_path):
                os.makedirs(work_dir_path)
            filepath = work_dir_path / 'config-datasets.yaml'
            with open(filepath, 'w') as f:
                f.write(config_dat_yaml)
            print(f'Created work dir: {work_dir_path}')


if __name__ == '__main__':
    main()
