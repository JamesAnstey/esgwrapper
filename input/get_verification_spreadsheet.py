#!/usr/bin/env python
'''
Usage:

./get_verification_spreadsheet.py validation_variables.json

Requires openpyxl. This env has it:
    /space/hall5/sitestore/eccc/crd/ccrn/users/rja001/miniconda3/envs/rja_publish_esgf_v1

'''

import argparse
import datetime
import json
import openpyxl as xp
import os
import urllib.request
from collections import OrderedDict


VERIFICATION_SPREADSHEET = {
    'url_google_sheet' : 'https://docs.google.com/spreadsheets/d/1JIF82CfKhTRhyHXDttRaTkaoMKpA9zRiESoX-zm77SA',
    'filename'         : 'validation_variables_dreq01.00.31.xlsx',
}


def parse_args():
    parser = argparse.ArgumentParser(
        description='Download validation spreadsheet information (Stamp of Approval)'
        )
    parser.add_argument('outfile', type=str,
                        help='name of output file (json)')
    parser.add_argument('-c', '--clobber', action='store_true', default=False,
                    help='automatically overwrite an existing file')
    return parser.parse_args()


def get_verification_spreadsheet(outfile, clobber=False):
    '''
    Download the verification (aka "validation") spreadsheet containing the Stamp of Approval
    for publishing variables. Save its contents to a json file that is read by the publishing
    script.
    '''

    # Ignore file extension, if input file has one
    outfile = os.path.splitext(outfile)[0]

    if not clobber:
        ld = os.listdir()
        ld = [s for s in ld if s.startswith(outfile)]
        if len(ld) > 0:
            print('Aborting because found existing files:')
            for s in ld:
                print(s)
            return

    # Get url of google spreadsheet
    url_google_sheet = VERIFICATION_SPREADSHEET['url_google_sheet']
    print('Downloading verification spreadsheet from:\n  {url}'.format(url=url_google_sheet))

    # Export the google spreadsheet as an xlsx file.
    ext = 'xlsx'
    urlname = os.path.join(url_google_sheet, 'export?exportFormat=' + ext)
    filepath = f'{outfile}.{ext}'
    urllib.request.urlretrieve(urlname, filepath)
    print('Downloaded: ' + filepath)

    # Write json file containing the spreadsheet info.
    wb = xp.load_workbook(filepath, read_only=True, data_only=True)
    print('Loaded spreadsheet: ' + filepath)
    sheets = wb.sheetnames
    d_vs = {} # dict to store spreadsheet contents. These are the default rules.
    d_override = {} # dict to store exceptions to the default rules (e.g. CaNOE biogeochemical variables).
    k_o = 0 # counter for override cases
    keep_sheets = ['atmos', 'land', 'ocean']
    override_sheets = ['ocean(canoe)'] # list of possible override sheets
    keep_sheets += override_sheets
    sheets = [s for s in sheets if s in keep_sheets]
    for sheet in sheets:
        ws = wb[sheet]
        # Read contents of the sheet into a list of lists (i.e. like a 2D matrix).
        row = []
        col0 = []
        headers_found = False
        ncol = None
        for k,r in enumerate(ws.rows):
            col = [c.value for c in r]
            if 'CMOR name' in col: 
                if len(col0) == 0:
                    # get column headers
                    headers_found = True
                    col0 = col
                    assert len(col0) == len(set(col0)) # no duplicate columns
                    m_cmorvar = col0.index('CMOR name')
                    ncol = len(col0)
                else:
                    # if column headers are repeated in the sheet, ensure that they match
                    assert col == col0
            if not headers_found: continue
            if col == col0: continue
            # Only add rows if the headers have been found. This stops us mistaking the 
            # example row for a data row.
            col = ['' if s in [None] else s for s in col] # replace None with ''
            while len(col) < ncol: col += ['']
            assert len(col) == ncol
            #if col[m_cmorvar] not in l_CMORvar: continue
            if col == ['']*ncol: 
                # Assume that empty row means the end of the list of CMOR variables.
                break
            row += [col]
        
        assert headers_found
        
        # Read sheet contents into dicts
        for col in row:
            if col == col0: continue  # in case the column headers occur partway through the table
            
            #d = {col0[k] : s for k,s in enumerate(col)} # create dict with named fields containing the column contents
            # revise above line to work in the ancient python version on the climres server
            d = {}
            for k,s in enumerate(col):
                d[col0[k]] = s
            
            #assert d['CMOR name'] in l_CMORvar # loop over spreadsheet rows, above, should have guaranteed that this is valid CMOR variable
            #t = tuple([str(s) for s in [d['CMOR name'], d['CMOR table']]])
            key = '.'.join([str(s) for s in [d['CMOR table'], d['CMOR name']]]) # e.g. "Amon.tas", "Omon.tos"
            
            if sheet in override_sheets:
                # These are the special cases, stored in a different part of the json file
                if sheet not in d_override:
                    # Create an entry for this override case.
                    d_override[sheet] = {'criteria' : [], 'variables' : {}, 'order' : k_o}
                    k_o += 1
                    # The reason to include an ordering index is so that the order of precedence
                    # for overrides is clear. This avoids the possibility of ambiguous logic when
                    # more than one override could apply to a given dataset.

                    # Set the criteria for which this override case applies.
                    # These are dataset parameters. If all of them have matches in a dataset under consideration,
                    # these this override applies to that dataset. For example:
                    #   dp = {'source_id': 'CanESM5-CanOE'}
                    # applies to any CanESM5-CanOE model run. Or,
                    #   dp = {'source_id': 'CanESM5', 'experiment_id' : 'amip'}
                    # applies to any CanESM5 amip run.
                    # The criteria are given as a list in case we want a given set of overrides to apply
                    # to more than one case.
                    l_dp = d_override[sheet]['criteria']
                    if      sheet in ['ocean(canoe)']:
                        dp = {'source_id': 'CanESM5-CanOE'}
                        l_dp.append(dp)
                    else:
                        raise Exception('Unknown override case: ' + sheet)
                
                assert key not in d_override[sheet]['variables']
                d_override[sheet]['variables'][key] = d
            
            else:
                # These are the default settings for this variable
                assert key not in d_vs # we shouldn't have already read in this variable - there is only one default setting!
                d_vs[key] = d
            
            if True:
                # Some quick fixes for formatting (19dec.19)
                # I put these in because I'm diffing json files to compare them.
                # Minor format issues can bloat the diff, making it harder to read.
                p = d_vs[key]['priority']
                if p not in ['']:
                    d_vs[key]['priority'] = float(p)
                if      key.startswith('priority for') \
                    or  key.startswith('Are we providing this variable') \
                    or  key.startswith('Not providing this variable'):
                    # These aren't variables, these are the colour legend!
                    d_vs.pop(key)
            
    # Rearrange d_vs and add metadata to d_vs giving origin of the info.
    d_vs = OrderedDict({
        'Header': {
            'xlsx source file': filepath,
            'created': datetime.datetime.now(datetime.timezone.utc).strftime('%d %b %Y %H:%M:%S UTC'),
        },
        'variables': d_vs,
        'variables override': d_override,
    })
    
    # Write out json file with the results
    filepath = outfile + '.json'
    with open(filepath, 'w') as f:
        w = json.dumps(d_vs, indent=2, sort_keys=True)
        f.write(w)
        os.chmod(filepath, 0o644)
        print('Wrote output file: ' + filepath)


if __name__ == '__main__':

    args = parse_args()

    print(args)

    get_verification_spreadsheet(
        args.outfile,
        clobber=args.clobber
        )


