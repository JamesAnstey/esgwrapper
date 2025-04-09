# esgwrapper

Thin wrapper around the [ESGF publishing software](https://esg-publisher.readthedocs.io/en/main/) that finds publishable datasets and loops over publishing commands.


## Running

### Setup

The CRD ESGF server cannot see the ECCC science network gitlab, so the wrapper can be "installed" on the server by cloning it to science and then copying the required files to the server, for which `server_sync.py` is a convenience utility:
```
git clone git@gitlab.science.gc.ca:rja001/esgwrapper.git
cd esgwrapper
./server_sync.py send *.py *.sh *.yaml input
```
(The copy location on the server is set in `server_sync.py`.)

### Workflow

Starting from science (e.g. `hprc-vis`):
```
ssh acrnpub@eccc-esgf.collab.science.gc.ca
cd /esg/publish/esgwrapper/
source setup.sh
```
Then set up a working dir for the publishing:
```
mkdir -p work/name_of_working_dir
cd work/name_of_working_dir
cp ../../config-datasets.yaml .
```
replacing `name_of_working_dir` with something sensible for the publishing being done.
It's not necessary to set up a new working dir every time - the reason to set one up is for convenience, so that previous publishing can be easily resumed or added to, based on a previous `config-datasets.yaml` file.
If re-using a previous working dir, simply cd to it after doing `source setup.sh` as noted above.

In the working dir, edit `config-datasets.yaml` to specify what datasets to publish by editing its `datasets` list. 
These entries can be broad (e.g., `CMIP6/CMIP/CCCma/CanESM5-1`) or more granular (e.g. `CMIP6/DCPP/CCCma/CanESM5/dcppB-forecast/s2022-r1i1p2f1/Amon`)
Additional specificity is possible with the `keep` and `exclude` filters.
The `paths` list gives all the top-level paths in which to search for datasets.
This can simply be all of the partitions on the CRD ESGF server, but specifying a subset will speed up the search.

The wrapper uses three steps to publish, all done by calling `publish` from the working dir using different command-line arguments (`publish` is an alias for `publish.py`).
The first is dataset discovery:
```
publish -d
```
which generates a file `datasets.json` specifying the datasets to publish.
This file is the input for the next two steps, generating mapfiles and then publishing. 
These are done in different conda envs, which are specified in `config-publisher.yaml` (the step will abort if the correct env is not activated).
To generate mapfiles, activate the required environment and then run:
```
publish -m
```
To publish datasets to ESGF, activate the required environment and then run:
```
publish -p
```

Verification of published datasets can be done by any available ESGF search method, such as with the [browser interface](https://aims2.llnl.gov/search) or a script-based tool like [search_esgf](https://gitlab.com/JamesAnstey/search_esgf).


### More details

To do a dry run of the mapfile or publish steps, invoke with the `-dry` option, e.g.
```
publish -p -dry
```
which will display the commands to stdout without running them.
Invoke `publish -h` to see other options.

If publishing **large datasets**, bigger than about 30 GB, v5.24 of the publisher can freeze due to memory issues on our system (as of April 2025).
[This was patched](https://github.com/ESGF/esg-publisher/issues/252) and the patch installed in the ESGF server's `esgf-pub524` env by:
```
pip install --upgrade --no-deps --force-reinstall 'git+https://github.com/sashakames/esg-publisher@patch-5.2.5-ncscan#subdirectory=src/python'
```
The option can be used for large datasets by first doing dataset discovery with a minimum size cutoff:
```
publish -d -min 20G
```
for example to only retain datasets bigger than 20 GB in the `datasets.json` file.
And then, after mapfile generation, invoke using the `--no-xarray` option:
```
publish -p --no-xarray
```
(Equivalently, the `esgpublish` command specified in `config-publisher.yaml` could be updated to include the `--no-xarray` argument; having this option for `publish` is simply a convenience to avoid having to update `config-publisher.yaml` based on the size of datasets being published.)

### Stamp of Approval

By default the "Stamp of Approval" is checked, blocking publication for unapproved variables (i.e., variables that have not been cleared for publication following examination by relevant scientists).
Information used by this check is stored in `input/validation_variables.json`.
The `-nv` option turns off this check (e.g. `publish -d -nv`), but this is not advised without good reason!


## Other information

### Adaptability

This config files have flexibility for other projects besides CMIP6, e.g. a `DRS` entry for file and directory naming conventions in `config-publisher.yaml`.
As of April 2025 only CMIP6 publishing has been tested, but it should be adaptable to, for example, CMIP7 or CORDEX-CMIP6 publishing.

Specifying publishing commands in `config-publisher.yaml` is intended to make the wrapper adaptable to future changes that may occur in the ESGF publishing software.

### History

An earlier, more complicated wrapper was used to publish CCCma CMIP6 datasets.
It was motivated by:
- ESGF publishing commands being somewhat complex
- Parallel processing to speed up publishing
- Logging to keep track of publisher errors and what was already published
- Quality control by filtering datasets according to the "Stamp of Approval"

Since then, the [ESGF publisher software](https://esg-publisher.readthedocs.io/en/main/) has been updated to make its workflow simpler, more robust, and faster.
A complex wrapper is not needed (and hard to maintain).
Further development of `esgwrapper` should keep it as simple as possible.
