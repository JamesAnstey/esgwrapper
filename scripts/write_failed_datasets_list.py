
import json

with open('failed_datasets.json') as f:
    d = json.load(f)
    dataset_ids = d['failed datasets']

outfile = 'failed_datasets.txt'
with open(outfile, 'w') as f:
    f.write('\n'.join(dataset_ids))
    print(f'Wrote {outfile}')

