#!/usr/bin/env python

import json
import os
import time
import urllib.request
from copy import deepcopy
from math import ceil

SEP_DATASET = '.'

def search(params,
           dataset_parameters,
           project,
           index_node, 
           include_replicas=False,
           verbose=False,
           show_browser_url=False,
           keep_params='all',
           ):

    project = project.lower()

    if keep_params != 'all':
        if keep_params is None:
            keep_params = []
        assert isinstance(keep_params, (list,set))
        assert all( [isinstance(p,str) for p in keep_params] )
        # User-requested parameters:
        keep_params_user = set(keep_params)
        # Parameters required internally by this function:
        keep_params = set(keep_params_user)
        keep_params.update(dataset_parameters)
        keep_params.update(['instance_id'])

    tmp_dir = '.tmp_esgf_search'
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    tmp_file = os.path.join(tmp_dir, 'tmp_search_results.json')

    search_filter = deepcopy(dict(params))

    if 'dataset' in search_filter:
        # In this case, a dataset or list of datasets has been specified.
        # Convert this here to a dict of parameters that can be processed
        # by the loop over l_filter below.
        lp = ['dataset', 'min_version', 'max_version']
        # Only parameters in lp will be used (if present), others are ignored.
        l = [p for p in search_filter if p not in lp]
        if len(l) > 0:
            print('Since dataset name is given, these other search filter parameters are ignored: ' + ', '.join(l))
        l = search_filter['dataset']
        lp.remove('dataset')
        if isinstance(l, STR_TYPES):
            l = [l]
        assert isinstance(l, list), 'search_filter[\'dataset\'] must be list or string'
        for dataset in l:
            stop  # fix later
            f = dsd(dataset)
            if len(f) == 0:
                if verbose:
                    print('Invalid dataset name: ' + dataset)
                continue
            for p in lp:
                if p in search_filter:
                    f[p] = search_filter[p]
            search_filter = f

    # Ensure each search filter only contains valid parameters
    if 'version' in search_filter:
        version = search_filter.pop('version')
        # Cannot search for a specific version, only a range of versions.
        # So if version is given, specify the min,max version to be the
        # specific version requested (i.e. specify a version range that
        # includes only the requested version).
        lp = ['min_version', 'max_version']
        for p in lp:
            if p in search_filter:
                # if min_version or max_version is already given, don't override it
                continue
            else:
                search_filter[p] = version_num(version, project)
                # note, min_version & max_version are given as version
                # numbers rather than version strings.
    lp = list(search_filter.keys())
    for p in lp:
        if search_filter[p] in ['', None]: search_filter.pop(p)

    # l_search = []
    # t_all_searches = time.time()
    n_found_something = 0
    n_found_nothing = 0
    # d_info = {'results by filter' : [], 'type' : 'ESGF search'}
    if len(search_filter) == 0:
        raise ValueError('Empty search filter')
    if verbose:
        print('\nSearching ESGF for these dataset parameters:')
        show_params(search_filter, dataset_parameters)

    lp = sorted(search_filter.keys()) # list of parameter names (aka search facets)

    # https://esgf-node.llnl.gov/projects/cmip6/
    #   The complete archive of CMIP6 output is made available for search and download via any one of the following portals:
    #   USA, PCMDI/LLNL (California) - https://esgf-node.llnl.gov/search/cmip6/
    #   France, IPSL - https://esgf-node.ipsl.upmc.fr/search/cmip6-ipsl/
    #   Germany, DKRZ - https://esgf-data.dkrz.de/search/cmip6-dkrz/
    #   UK, CEDA - https://esgf-index1.ceda.ac.uk/search/cmip6-ceda/

    index_node = 'esgf-node.llnl.gov'
    
    # Note: this corresponds to the "index_node" parameter that will be returned in the
    # search results metadata.

    if show_browser_url:
        # In case it's useful, show the user a URL that can be cut-paste into the browser URL bar
        # to bring up the same search results in the usual ESGF search view (i.e. the point-click
        # interface). This can be handy to verify the results, or perhaps is a more convenient
        # way to view the metadata, etc.
        #
        # Example of such a URL:
        #   https://esgf-node.llnl.gov/search/cmip6/?&limit=100&source_id=CanESM5&table_id=Amon

        limit = 100 # 100 seems to be the max possible for the browser view. The default is 10.

        # lq = ['https://{}/search/cmip6/?limit={}'.format(index_node, limit)]

        lq = [f'https://{index_node}/search/{project}/?limit={limit}']

        for p in lp:
            if isinstance(search_filter[p], (list,tuple)):
                s = ','.join([str(s) for s in search_filter[p]])
            else:
                s = search_filter[p]
            if p == 'member_id':
                # This is odd, but it seems that the cut-paste URL syntax wants a different
                # name for this parameter.
                # (Note, if an incorrect parameter name is passed to the URL, it doesn't produce
                # an error, it just gets ignored. So failing to pass the desired member_id will
                # result in all available ensemble members being returned by the search.)
                p = 'variant_label'
            lq += ['&{}={}'.format(p,s)]
        urlname = ''.join(lq)
        print('To see the same search results in ESGF web search view, cut-paste this URL into your browser:')
        print('\n    ' + urlname)

    limit = 10000
    # The "limit" parameter the maximum number of datasets that can be returned for a given search. It appears
    # that this can be set to any value up to 10000. Since it's possible that a query could return more than
    # 10000 datasets, the loop below will keep repeating the search until all datasets have been found. The
    # "offset" parameter sets how many datasets (out of all available for the given search) to skip before
    # returning a set of results. It's analogous to the "Display N results per page" box on the ESGF website,
    # where you can set N = 10, 20, 50, or 100. Supposing you used N=10, then offset=0 corresponds to the first
    # page of results, offset=10 the second page of results, and so on.
    #
    # I'm not sure if there's any reason to set "limit" to anything other than 10000, but it doesn't really
    # matter what it's set to. The search will continue until all available datasets are returned. "limit"
    # just determines how many queries to the ESGF are required to do that. There might be an optimal value
    # for most efficient searching, but the search is so fast that I'd guess it doesn't matter.

    assert limit > 0 and limit <= 10000, 'Set "limit" to a positive integer not greater than 10000'
    offset = 0
    keep_searching = True
    first_search = True
    n_search = 0
    t_search = time.time()
    while keep_searching:
        # Create URL containing instructions for the search.
        lq  = ['https://{}/esg-search/search/'.format(index_node)]
        lq += ['?offset={}'.format(offset)]
        lq += ['&limit={}'.format(limit)]
        lq += ['&type=Dataset']
        if include_replicas:
            lq += ['&replica=true']
        else:
            lq += ['&replica=false']

        find_latest_version_only = True
        #if ('min_version' in search_filter) and ('max_version' in search_filter):
        # seems no reason to require both min & max; it works if only one is given
        #if ('min_version' in search_filter) or ('max_version' in search_filter):
        l = ['min_version', 'max_version']
        if any( [p in search_filter for p in l] ):
            find_latest_version_only = False
            # If not restricting the search to just the latest version of any given dataset, the search
            # will return all versions falling within the date ranges given. E.g. 
            #   'min_version'   : 20190301,
            #   'max_version'   : 20190424,
            # It works as <=, >= operators, i.e. min_version=20190306 will return a version v20190306, but
            # not v20190305.
            # Note, min_version & max_version are pass to the ESGF search as numbers (e.g. 20190306),
            # not as version strings (e.g. 'v20190306').
            for p in l:
                if p not in search_filter: continue
                if isinstance(search_filter[p], (list, tuple)):
                    # In general the parameters in search_filter are allowed to be lists.
                    # But for min_version & max_version this doesn't make sense, there can only be one value.
                    assert len(search_filter[p]) == 1
                    search_filter[p] = search_filter[p][0]
                search_filter[p] = version_num(search_filter[p], project) # ensure version is a number (will convert from str to int if needed)

        if find_latest_version_only:
            lq += ['&latest=true']
        # lq += ['&project=CMIP6']
        lq += [f'&project={project.upper()}']

        for p in lp:
            if isinstance(search_filter[p], (list,tuple)):
                s = ','.join(search_filter[p])
            else:
                s = search_filter[p]
            lq += ['&{}={}'.format(p,s)]
        lq += ['&format=application%2Fsolr%2Bjson']
        urlname = ''.join(lq)
        # urlname (str) now contains the search URL. If this were cut-pasted into a web browser it would return the
        # json file containing the search results
        
        
        if verbose:
            print('\nSearching ESGF using search URL:')
            print(' '*2 + urlname)
        
        urllib.request.urlretrieve(urlname, tmp_file)
        with open(tmp_file, 'r') as f:
            d_json = json.load(f)
        numFound = d_json['response']['numFound']
        num_docs = len(d_json['response']['docs'])
        n_search += 1

        # Allow for possibility of numFound changing while search is
        # being done. This can happen if data satisfying the search
        # criteria is being published simultaneously while the search
        # is conducted.
        #
        # Previously the code recorded numFound from the first search
        # as numFound0 and checked it matched the value of numFound in
        # all subsequent searches. This was meant to check the
        # consistency of the results. However it doesn't seem to be
        # needed. On each iteration of this loop ("while keep_searching")
        # the whole search is done again but the "offset" and "limit"
        # parameters are used to limit the number of dataset for which
        # info is actually returned (this seems to be a necessity with
        # the ESGF search). So I don't know any reason why numFound
        # can't change while the search is being done.
        if numFound > 0:
            n_found_something += 1
        else:
            n_found_nothing += 1
                
        total_size = sum([d['size'] for d in d_json['response']['docs']])
        number_of_files = sum([d['number_of_files'] for d in d_json['response']['docs']])
        if verbose:
            #print('Search results:')
            expected_number_of_searches = int(ceil( numFound/float(limit) ))
            print('Search results ({0} of {1} expected searches):'.format(n_search, expected_number_of_searches))
            if num_docs < numFound:
                print('  {0} datasets were found using the current search URL (out of {1} total available datasets)'.format(num_docs, numFound))
            else:
                print('  {0} datasets were found using the current search URL'.format(num_docs))
            print('  total size: {0}, total number of files: {1}'.format(file_size_str(total_size), number_of_files))
        if num_docs == 0: 
            break

        if keep_params != 'all':
            # Keep only specified parameters in each dict belonging to the "docs" list.
            for k,d in enumerate(d_json['response']['docs']):
                keep_params1 = [p for p in keep_params if p in d] # filter out any parameters that are missing from dict d
                d_json['response']['docs'][k] = dict([ (p,d[p]) for p in keep_params1 ])
                # Note, the above line uses this nice syntax for creating a dict:
                #   dict([('a',1), ('b',2)]) --> {'a': 1, 'b': 2}
        
        d_search = {
            'search' : {
                'filter'    : search_filter,
                'limit'     : limit,
                'offset'    : offset,
                },
            'results' : d_json,
        }
        # l_search += [d_search]
        
        if num_docs < limit:
            keep_searching = False
        else:
            assert num_docs == limit # if I understand the ESGF search correctly, this is guaranteed
            offset += num_docs
    
    t_search = time.time() - t_search
    if verbose:
        print('Time taken for search: {0} s'.format('%.3g' % t_search))

    # print(d_json['response'].keys())
    # print(d_json['response']['numFound'])

    d_found = {}
    d_query = {}

    dr = d_search['results']
    docs = dr['response']['docs']
    for doc in docs:
        # Create dict of parameters defining the dataset
        params = {}
        for p in dataset_parameters:
            if isinstance(doc[p], (list,tuple)):
                assert len(doc[p]) == 1
                params[p] = doc[p][0]
            else:
                params[p] = doc[p]
            if p in ['version']:
                if project in ['cmip6']:
                    params[p] = 'v' + params[p]
                else:
                    raise ValueError('Unknown project: ' + project)

        # Use this dict to create the dataset id string
        dataset = SEP_DATASET.join([params[p] for p in dataset_parameters])

        # Validate the dataset id string
        assert dataset == doc['instance_id']

        if keep_params != 'all':
            # Retain only requested parameters in doc dict
            keep_params1 = [p for p in keep_params_user if p in doc]
            doc = {p : doc[p] for p in keep_params1}

        doc.setdefault('replica', False) # ensure replica flag is set

        if dataset not in d_found:
            d_found[dataset] = {
                'doc'       : [],
                'params'    : params,
            }
            d_query[dataset] = []
        else:
            # If already found an instance of this dataset, ensure its parameters are consistent with the new one found
            assert d_found[dataset]['params'] == params

        d_found[dataset]['doc'].append(doc)
        d_query[dataset].append(d_search['search'])

    # TO DO:
    #   what is d_query for?
    #   root out any other cmip6 assumptions (want this to work for any project)

    return d_found


def check_version_format(version, project):
    '''Return True if version string or version integer (aka the version date)
    is in the correct format.
    
    Example of version string in correct format: "v20190306"
    Example of version integer of correct length:  20190306
    
    Unlike all other parameters that make up dataset names, the version string
    is not part of the CMIP6 controlled vocabulary. Hence there's nothing in
    the data conversion pipeline to stop a version string being "this_version"
    or whatever. But CMIP6 guidance requests that version be a string of the
    form "v" followed by the date given as YYYYMMDD (also referred to above as
    the version integer).
    '''
    ok = False
    if project.lower() in ['cmip6']:
        if isinstance(version, str):
            s = version.strip('v')
            ok =    len(version) == 9 \
                and version.startswith('v') \
                and version.count('v') == 1 \
                and s.isdigit() \
                and len(s) == 8
            if ok:
                # check the actual value of the integer date is ok
                ok = check_version_format(int(s), project)
        elif isinstance(version, int):
            s = str(version)
            month = int(s[4:6])
            day =   int(s[6:8])
            ok =    len(s) == 8 \
                and (month >= 1 and month <= 12) \
                and (day   >= 1 and day   <= 31)
    else:
        raise ValueError(f'Unknown project: ' + project)
    return ok


def version_num(version, project):
    '''Return version integer based on input that's either string or integer.
    E.g. "v20190306" --> 20190306
    If input is already a valid version integer then it's returned unchanged.
    '''
    if project.lower() in ['cmip6']:
        v = None
        if check_version_format(version, project):
            if isinstance(version, str):
                v = int(version.strip('v'))
            elif isinstance(version, int):
                v = version
    else:
        raise ValueError(f'Unknown project: ' + project)
    return v


def show_params(params, dataset_parameters, indent='', return_str=False):
    '''Pretty print of a parameters dict. Only purpose is to show the parameters
    in the same order as they appear in dataset_parameters. This makes it easier
    to compare the contents of params with the name of a dataset. E.g. for dataset
    name of
    
        CMIP6.ScenarioMIP.CCCma.CanESM5.ssp245.r10i1p1f1.LImon.snm.gn.v20190429   
    
    the corresponding filter dict (i.e. the filter that will grab only this
    dataset) is
    
        params = {
            'mip_era'        : 'CMIP6'
            'activity_drs'   : 'ScenarioMIP'
            'institution_id' : 'CCCma'
            'source_id'      : 'CanESM5'
            'experiment_id'  : 'ssp245'
            'member_id'      : 'r10i1p1f1'
            'table_id'       : 'LImon'
            'variable_id'    : 'snm'
            'grid_label'     : 'gn'
            'version'        : 'v20190429'
        }
    
    and the above display is how show_params(params) shows the dict.
    '''
    l = ['{']
    m = max([len(p) for p in dataset_parameters])
    show_apostrophes = not True
    if show_apostrophes: m += 2
    fmt = '%-{}s'.format(m)
    # Display the keys from dataset_parameters, if present.
    # Also catch any keys in params that aren't in dataset_parameters.
    lk = sorted([k for k in params.keys() if k not in dataset_parameters])
    for k,p in enumerate(dataset_parameters + lk):
        if p not in params: continue
        ls = [p, params[p]]
        for k in range(len(ls)):
            if not isinstance(ls[k], str):
                ls[k] = str(ls[k])
        if show_apostrophes:
            for k in range(len(ls)):
                if isinstance(ls[k], str):
                    ls[k] = '\'{}\''.format(ls[k])
        l += ['    {} : {}'.format(fmt % ls[0], ls[1])]
    l += ['}']
    l = [indent + s for s in l]
    if return_str:
        return '\n'.join(l)
    else:    
        print('\n'.join(l))


def file_size_str(a):
    '''Given file size in bytes, return string giving the size in nice
    human-readable units (like ls -h does at the shell prompt.'''

    SIZE_PREFIX_MULTIPLE = 1024.  # 1 MB = 1024 KB, 1 GB = 1024 MB, etc
    # SIZE_PREFIX_MULTIPLE = 1000.  # 1 MB = 1000 KB, 1 GB = 1000 MB, etc 

    m = SIZE_PREFIX_MULTIPLE
    d_b = {
        'B' : 1.
    ,   'KB': 1 / m
    ,   'MB': 1 / m**2
    ,   'GB': 1 / m**3
    ,   'TB': 1 / m**4
    ,   'PB': 1 / m**5
    }
    # list of units, in order of descending size of the unit
    uo = sorted([(d_b[s], s) for s in d_b])
    # choose the most sensible size to display
    for tu in uo:
        if (a*tu[0]) > 1: break
    su = tu[1]
    a *= tu[0]
    sa = str('%.3g' % a)
    return sa + ' ' + su

