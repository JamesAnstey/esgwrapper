#!/usr/bin/env python
'''
Analyse times for command execution as recorded in publish.py logfile
'''


# text = """463:SUCCESS - exit_status: 0, attempts: 1, time: 102.4729 s
# 467:SUCCESS - exit_status: 0, attempts: 1, time: 15.7973 s
# 471:SUCCESS - exit_status: 0, attempts: 1, time: 89.4033 s
# 475:SUCCESS - exit_status: 0, attempts: 1, time: 65.9726 s
# 479:SUCCESS - exit_status: 0, attempts: 1, time: 58.2070 s"""


import argparse
import numpy as np
import re

parser = argparse.ArgumentParser()
parser.add_argument('filename', type=str, help='logfile to parse')
args = parser.parse_args()

filename = args.filename
with open(filename) as f:
    text = f.read()

# Matches any decimal number right before the trailing ' s'
numbers = [float(num) for num in re.findall(r'([0-9.]+)\s+s$', text, re.MULTILINE)]
# print(numbers)

times = np.array(numbers)
print(f'no. of datasets: {len(times)}')
print(f'average time: {times.mean()}')
print(f'median time: {np.median(times)}')
print(f'max, min times: {times.max()}, {times.min()}')
tot = times.sum()
print(f'total time: {tot} s ({tot/60} min, {tot/3600} hr)')