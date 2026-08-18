# esgwrapper

Wrapper for [ESGF publishing software](https://esg-publisher.readthedocs.io/en/main/) that finds publishable datasets and loops over publishing commands.


### Workflow

On server where publishing commands will be run:
```bash
source setup.sh  # must be in repo top-level dir
mkdir -p work/name_of_working_dir  # set up working dir for publishing
cd work/name_of_working_dir
cp ../../esg_ng/config-datasets.yaml .
cp ../../esg_ng/esgcet_files/esg_east.yaml .
```
If re-using a previous working dir, simply cd to it after doing `source setup.sh`.

In the working dir, edit `config-datasets.yaml` to specify what datasets to publish by editing its `datasets` list. 
These entries can be broad (e.g., `CMIP6/CMIP/CCCma/CanESM5-1`) or more granular (e.g. `CMIP6/DCPP/CCCma/CanESM5/dcppB-forecast/s2022-r1i1p2f1/Amon`)
Additional specificity is possible with the `keep` and `exclude` filters.
The `paths` list gives all the top-level paths in which to search for datasets.

The wrapper uses three steps to publish, all done by calling `publish` from the working dir using different command-line arguments (`publish` is an alias for `publish.py`).
The first is dataset discovery:
```bash
publish -d -c7
```
which generates a file `datasets.json` specifying the datasets to publish.
The `-c7` option prevents already-published CMIP7 datasets from being included in `datasets.json`.

⚠️ **TODO: replace ad-hoc `-c7` option with a proper ESGF search using the search API or esgpull**

The `datasets.json` file is the input for the next two steps, generating mapfiles and then publishing. 
These will abort if the correct env is not activated (indicated in `config-publisher.yaml`), and a message will be displayed on stdout saying how to activate the correct env.
To generate mapfiles:
```bash
publish -m
```
To publish datasets to ESGF:
```bash
publish -p
```
The publish command allows for retries in case it fails, e.g. `publish -p -r 2` to retry twice if the first attempt fails.

### Test commands before publishing

To do a dry run of the mapfile or publish steps, invoke with the `-dry` option, e.g.
```bash
publish -p -dry
```
which will display the commands to stdout without running them.
This is useful to verify that the wrapper will indeed execute the expected commands.

### Data request

⚠️ **TODO: update for CMIP7 Data Request**

By default the discovered datasets are filtered by the project's data request, retaining only requested variables.
This makes use of an input file specifying the variables requested for each experiment, provided in `input/`. 
If setting up a new project and filtering by data request is desired, a file specifying its requested variables will need to be provided and the relevant functions in `tools.py` updated accordingly.

Filtering by data request can be turned off with the `-ndreq` ("no data request") flag:
```bash
publish -d -ndreq
```

Information about dataset size and filenames is included in the produced `datasets.json` file.
This is useful to find out what volume of data will be published, and potentially to check for [large datasets](#large-datasets) that might cause publisher problems.

### Stamp of Approval

⚠️ **TODO: update for CMIP7 validations**

By default approval status of a variable is checked, blocking publication for unapproved variables (i.e., variables that have not been cleared for publication following examination by relevant scientists).
Information used by this check is stored in `input/validation_variables.json`.
The `-nval` option turns off this check (e.g. `publish -d -nval`).
However the check is intended to prevent publication of unvalidated data and it should **not** be turned off without good reason.

### Large datasets

The option can be used for large datasets by first doing dataset discovery with a minimum size cutoff:
```bash
publish -d -min 20G
```
for example to only retain datasets bigger than 20 GB in the `datasets.json` file. 
(There is also a `-max` option to retain only datasets smaller than a certain size; the `-min` and `-max` options can also be combined to search for datasets within a size range.)

### Inventory

The `datasets.json` file is basically an inventory of datasets in the paths specified by `config-datasets.json`, which is filtered in various ways including (by default) searching ESGF to see which datasets are already published and checking if variables are approved for publication.
To simply produce an inventory of all local datasets, invoke the discovery step using the `-nesgf` ("no ESGF search") and `-nval` ("no validation") flags:
```bash
publish -d -nesgf -ndreq -nval
```
with `keep` and `exclude` in `config-datasets.yaml` being empty (unless some filtering is desired).
For convnience, option `-i` does the same thing as above, and also renames the output file `inventory.json`:
```bash
publish -i
```

## Other information

### Adaptability

This config files have flexibility for other projects besides CMIP6, e.g. a `DRS` entry for file and directory naming conventions in `config-publisher.yaml`.

Specifying publishing commands in `config-publisher.yaml` is intended to make the wrapper adaptable to future changes that may occur in the ESGF publishing software.
