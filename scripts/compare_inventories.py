#!/usr/bin/env python
'''
Run invnentory on a dir (publish -i) and then compare the size of datasets found to result of du on the dir.
Use this to check if inventory is finding as much data as we expect.
'''

import json
import os
import subprocess
import sys
import time

from pathlib import Path

from esgwrapper.utils.tools import load_config_file
from esgwrapper.utils.esgfsearch import file_size_str

# os.system('publish -i')
cmd = 'publish -i'
result = subprocess.Popen(
    cmd.split(),
    stdout=subprocess.PIPE,
    text=True
)
for line in result.stdout:
    print(line.strip())

config_dat = load_config_file('config-datasets.yaml')

# Allow only one line each for "paths" and "inventory" in the config file.
# (Easier and general enough for purposes of this script.)
assert len(config_dat['paths']) == 1
assert len(config_dat['inventory']) == 1

dirpath = config_dat['inventory'][0]
base_path = config_dat['paths'][0]

time_taken = time.time()
# cmd = f'du -h --max-depth=0 {Path(base_path) / Path(dirpath)}'
cmd = f'du -b --max-depth=0 {Path(base_path) / Path(dirpath)}'

os.system(cmd)

result = subprocess.Popen(
    cmd.split(),
    # stdout=sys.stdout, # preserves colour (if any) in the stdout
    # stderr=sys.stderr,
    stdout=subprocess.PIPE,
    # stderr=subprocess.PIPE,
    text=True,
)
stdout, stderr = result.communicate()
# exit_status = result.returncode
size_du = int(stdout.split('\t')[0])

time_du = time.time() - time_taken
# print(f'time taken (s): {time_taken}')

with open('inventory.json') as f:
    d = json.load(f)
    size_inventory = d['Header']['total size (bytes)']
    time_inventory = d['Header']['time taken (s)']


time_ratio = time_inventory / time_du
size_ratio = size_inventory / size_du


fmt = '%.6f'
msg = f'''
base path: {base_path}
datasets:  {dirpath}
time taken (s):
  du:        {time_du}
  inventory: {time_inventory}
  inventory / du: {fmt % time_ratio} 
size (bytes):
  du:        {size_du}  ({file_size_str(size_du)})
  inventory: {size_inventory}  ({file_size_str(size_inventory)})
  inventory / du: {fmt % size_ratio} 
'''
print(msg)
