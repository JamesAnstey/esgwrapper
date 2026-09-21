'''
Testing generate_mapfiles.py

Load mapfiles from one dir, compare the contents of mapfiles with same filenames in another
'''

import os
from pathlib import Path

path = Path('mapfiles4')

filenames = os.listdir(path)

path2 = Path('mapfiles_from_server')
filenames2 = os.listdir(path2)

for filename in filenames:
    print(f'\nChecking mapfile {filename}')

    if filename not in filenames2:
        print(f'--> File not found in {path2}, skipping')
        continue

    with open(path / filename) as f:
        w = f.read()
    lines = w.split('\n')

    with open(path2 / filename) as f:
        w = f.read()
    lines2 = w.split('\n')

    assert len(lines) == len(lines2)
    assert len(set(lines)) == len(set(lines2))

    ok = True
    if lines != lines2:
        print('lines differ')
        lines = sorted(lines)
        lines2 = sorted(lines2)
        if lines == lines2:
            print('after sorting, lines are the same')
            ok = True
        else:
            print('lines still differ after sorting')
            ok = False
    if set(lines) != set(lines2):
        print('line contents differ')
        ok = False

    if ok:
        print('* mapfiles agree *')
        