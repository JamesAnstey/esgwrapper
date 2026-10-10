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


MAPFILES_DIRNAME = 'mapfiles'
SYNC_SCRIPT = 'sync_to_server.sh'


def parse_args():
    parser = argparse.ArgumentParser(
        description=dedent(f'''\
            Set up one or more working directories for ESGF publishing.
            Work dirs will be created in: {WORK_DIRS_LOCATION}
            -u can be used to update existing work dir files.
            -ud, -ue allow updates of single files.
            '''), formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('-c', '--config', type=str, default=DEFAULT_WORKDIRS_CONFIG_FILE,
                        help='config file specifying how to set up working directories, default: %(default)s')
    parser.add_argument('-u', '--update', action='store_true',
                        help='overwrite files in existing work dirs')
    parser.add_argument('-ud', '--update-datasets', action='store_true',
                        help='overwrite only the datasets config file in existing work dirs')
    parser.add_argument('-ue', '--update-esgcet', action='store_true',
                        help='overwrite only the ESGF publisher config file in existing work dirs')
    parser.add_argument('-np', '--no-prompt', action='store_true',
                        help='do not prompt user to confirm work dir creation')
    parser.add_argument('-cd', '--config-datasets', type=str, default=DEFAULT_DATASETS_CONFIG_FILE,
                        help='name of datasets config file to write in work dir, default: %(default)s')

    return parser.parse_args()


class WorkDir(dict):
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


class WriteFlags():
    def __init__(self):
        self.write_config_datasets = False
        self.write_config_esgcet = False
        self.write_sync_script = False
    def __repr__(self):
        return str(self.__dict__)
    def write_all(self):
        self.write_config_datasets = True
        self.write_config_esgcet = True
        self.write_sync_script = True
    def any(self):
        return any([
            self.write_config_datasets,
            self.write_config_esgcet,
            self.write_sync_script
        ])


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
    esgcet_config_file = config_pub['publish']['esgcet_config_file']

    # Get parameters that will be used by all work dirs unless overridden
    base_config = WorkDir(**config_wrk)

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

        # Figure out what to write
        flags = WriteFlags()  # initializes all flags to False
        if args.update_datasets:
            flags.write_config_datasets = True
        if args.update_esgcet:
            flags.write_config_esgcet = True
        if args.update:
            flags.write_all()
        if work_dir_path.exists():
            # Dir already exists, so only proceed if there are updates to make
            if not flags.any():
                print(f'\nWork dir already exists: {work_dir_path}')
                continue
        else:
            # Dir doesn't exist, so write everything
            flags.write_all()

        config_dat_yaml = yaml.safe_dump(config_dat, default_flow_style=False, sort_keys=False)
        if prompt_user:
            print(f'\nWork dir path:\n  {work_dir_path}')
            if flags.write_config_datasets:
                print(f'\n{args.config_datasets} parameters:')
                print(indent(config_dat_yaml, '  '))
            print('Files to write:')
            if flags.write_config_datasets:
                print(f'  {args.config_datasets}')
            if flags.write_config_esgcet:
                print(f'  {esgcet_config_file}')
            if flags.write_sync_script:
                print(f'  {SYNC_SCRIPT}')
            if not work_dir_path.exists():
                print(f'Set up {work_dir_name} work dir?')
            ok = input('ENTER or "y" for yes, anything else for no: ')
        else:
            ok = ''
        if ok in ['', 'y']:
            work_dir_path.mkdir(parents=True, exist_ok=True)

            files_to_sync = []

            if flags.write_config_datasets:
                # Create datasets config file in the work dir
                filename = args.config_datasets
                outfile = work_dir_path / filename
                with open(outfile, 'w') as f:
                    f.write(config_dat_yaml)
                files_to_sync.append(filename)
                print(f'Wrote {args.config_datasets}')

            if flags.write_config_esgcet:
                # Copy publisher config file to work dir
                filename = esgcet_config_file
                shutil.copy( ESGCET_CONFIG_FILES_DIR / filename, work_dir_path / filename)
                files_to_sync.append(filename)
                print(f'Wrote {esgcet_config_file}')

            # Create dir for mapfiles, if it doesn't already exist
            # If updating an existing work dir, the mapfiles dir will NOT be overwritten
            # (that would be bad - it can take a while to compute mapfiles)
            mapfiles_path = work_dir_path / MAPFILES_DIRNAME
            mapfiles_path.mkdir(parents=True, exist_ok=True)
            files_to_sync.append(MAPFILES_DIRNAME)

            if flags.write_sync_script:
                # Create script to sync work dir to ESGF server
                server = config_wrk['server']
                user = server['user']
                hostname = server['hostname']
                work_dir_path_on_server = Path(server['work_dirs_location'])
                # file_list = ' '.join(files_to_sync)
                script_contents = dedent(f'''\
                    # Create work dir on server (no effect if dir already exists)
                    ssh {user}@{hostname} "mkdir -p {work_dir_path_on_server / work_dir_name}"
                    # Sync files to work dir on server
                    ''')
                for file in files_to_sync:
                    script_contents += f'rsync -tpur {file} {user}@{hostname}:{work_dir_path_on_server / work_dir_name}\n'

                outfile = work_dir_path / SYNC_SCRIPT
                with open(outfile, 'w') as f:
                    f.write(script_contents)
                # Set script to have user execute permission
                permissions = os.stat(outfile).st_mode
                new_permissions = permissions | stat.S_IXUSR
                os.chmod(outfile, new_permissions)

            print(f'{work_dir_name} work dir is ready:\n  {work_dir_path}')

        else:
            print(f'Skipping {work_dir_name}')


if __name__ == '__main__':
    main()
