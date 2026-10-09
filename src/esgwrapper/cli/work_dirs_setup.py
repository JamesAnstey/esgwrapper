#!/usr/bin/env python
'''
Set up working dir(s) for publishing.
'''

import argparse
import os
import shutil
import stat
import yaml

from copy import deepcopy
from pathlib import Path
from textwrap import indent, dedent

from esgwrapper import (CONFIG_FILES_DIR, ESGCET_CONFIG_FILES_DIR, DEFAULT_DATASETS_CONFIG_FILE, REPO_DIR,
                        DEFAULT_WORKDIRS_CONFIG_FILE, WORK_DIRS_LOCATION)
from esgwrapper.utils.tools import load_config_file

DEFAULT_ESGCET_CONFIG_FILE = 'esg_east.yaml'

def parse_args():
    esgcet_rel_path = ESGCET_CONFIG_FILES_DIR.relative_to(REPO_DIR)
    m = max(len(DEFAULT_DATASETS_CONFIG_FILE), len(DEFAULT_ESGCET_CONFIG_FILE))
    fmt = f'%-{m}s'
    parser = argparse.ArgumentParser(
        description=dedent(f'''\
            Set up one or more working directories for ESGF publishing.
            Work dirs will be created in: {WORK_DIRS_LOCATION}

            With the -u option, these files in an existing work dir will be overwritten:
                {fmt % DEFAULT_DATASETS_CONFIG_FILE}  (or use -cd to change name)
                {fmt % DEFAULT_ESGCET_CONFIG_FILE}  (or use -ce to select a different file from {esgcet_rel_path})
                sync_to_server.sh
            Nothing else in an existing work dir will be affected (the mapfiles directory will never be overwritten).

            With the -ud option, only {DEFAULT_DATASETS_CONFIG_FILE} (or -cd for different name) is overwritten.
            '''), formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('-c', '--config', type=str, default=DEFAULT_WORKDIRS_CONFIG_FILE,
                        help='config file specifying how to set up working directories, default: %(default)s')
    parser.add_argument('-u', '--update', action='store_true',
                        help='overwrite files in existing work dirs')
    parser.add_argument('-ud', '--update-datasets', action='store_true',
                        help='overwrite only the datasets config file in existing work dirs\
                              (takes precedence over -u)')
    parser.add_argument('-np', '--no-prompt', action='store_true',
                        help='do not prompt user to confirm work dir creation')
    parser.add_argument('-cd', '--config-datasets', type=str, default=DEFAULT_DATASETS_CONFIG_FILE,
                        help='datasets config file to write in work dir, default: %(default)s')
    parser.add_argument('-ce', '--config-esgcet', type=str, default=DEFAULT_ESGCET_CONFIG_FILE,
                        help=f'ESGF publisher config file to copy into the work dir, default: %(default)s\
                             (available files in {esgcet_rel_path})')

    return parser.parse_args()


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
        use_attrs = []
        use_attrs.append('activity_id')
        use_attrs.append('source_id')
        use_attrs.append('experiment_id')
        for attr in use_attrs:
            if attr in self.inventory:
                dir_name += f'_{self.inventory[attr]}'
        return dir_name


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

    # Set up work dirs
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

        # Create dict to write a config-datasets.yaml in the work dir
        # (file can have a different name if passed by -cd option)
        config_dat = {
            'project': wrk.project,
            'inventory': [path],
        }
        if wrk.keep:
            config_dat['keep'] = wrk.keep
        if wrk.exclude:
            config_dat['exclude'] = wrk.exclude
        config_dat['paths'] = wrk.paths

        work_dir_name = wrk.dir_name()
        work_dir_path = WORK_DIRS_LOCATION / work_dir_name
        update_work_dir = args.update or args.update_datasets
        if os.path.exists(work_dir_path) and not update_work_dir:
            print(f'\nWork dir already exists: {work_dir_path}')
            continue

        config_dat_yaml = yaml.safe_dump(config_dat, default_flow_style=False, sort_keys=False)
        if prompt_user:
            print(f'\nWork dir path:\n  {work_dir_path}')
            print(f'\n{args.config_datasets} parameters:')
            print(indent(config_dat_yaml, '  '))
            how_to_respond = ' (ENTER or "y" for yes, anything else for no): '
            if args.update_datasets:
                msg = f'Update {args.config_datasets} in {work_dir_name}?{how_to_respond}'
            elif args.update:
                msg = f'Update files in {work_dir_name}?{how_to_respond}'
            else:
                msg = f'Set up {work_dir_name} work dir?{how_to_respond}'
            ok = input(msg)
        else:
            ok = ''
        if ok in ['', 'y']:
            if not os.path.exists(work_dir_path):
                os.makedirs(work_dir_path)

            files_to_sync = []

            # Create datasets config file in the work dir
            filename = args.config_datasets
            outfile = work_dir_path / filename
            with open(outfile, 'w') as f:
                f.write(config_dat_yaml)
            files_to_sync.append(filename)
            if args.update_datasets:
                # Only this update is requested, skip the other ones below
                print(f'Wrote {args.config_datasets}')
                continue

            # Copy publisher config file to work dir
            filename = args.config_esgcet
            shutil.copy( ESGCET_CONFIG_FILES_DIR / filename, work_dir_path / filename)
            files_to_sync.append(filename)

            # Create dir for mapfiles, if it doesn't already exist
            # If updating an existing work dir, the mapfiles dir will NOT be overwritten
            # (that would be bad - it can take a while to compute mapfiles)
            mapfiles_dirname = 'mapfiles'
            mapfiles_path = work_dir_path / mapfiles_dirname
            if not os.path.exists(mapfiles_path):
                os.makedirs(mapfiles_path)
            files_to_sync.append(mapfiles_dirname)

            # Create script to sync work dir to ESGF server
            server = config_wrk['server']
            user = server['user']
            hostname = server['hostname']
            work_dir_path_on_server = Path(server['work_dirs_location'])
            script_filename = 'sync_to_server.sh'
            # file_list = ' '.join(files_to_sync)
            script_contents = dedent(f'''\
                # Create work dir on server (no effect if dir already exists)
                ssh {user}@{hostname} "mkdir -p {work_dir_path_on_server / work_dir_name}"
                # Sync files to work dir on server
                ''')
            for file in files_to_sync:
                script_contents += f'rsync -tpur {file} {user}@{hostname}:{work_dir_path_on_server / work_dir_name}\n'

            outfile = work_dir_path / script_filename
            with open(outfile, 'w') as f:
                f.write(script_contents)
            # Set script to have user execute permission
            permissions = os.stat(outfile).st_mode
            new_permissions = permissions | stat.S_IXUSR
            os.chmod(outfile, new_permissions)

            print(f'{work_dir_name} work dir is ready:\n  {work_dir_path}')

        else:
            print(f'Skipping {work_dir_name} work dir creation')



if __name__ == '__main__':
    main()
