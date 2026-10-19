# esgwrapper

### Installation

⚠️ TODO: clarify science-side and server-side setup.

Create a venv into which the software will be installed:
```bash
python3.12 -m venv esgpub  # or whatever env name you like
source esgpub/bin/activate
pip install --upgrade pip
```
Then (still in the activated venv) go to directory where the software and work dirs will live and install it:
```bash
cd /datalocal/home/scrd106/esgf_publishing/cmip7  # this is server path, but can install on science as well
git clone git@github.com:JamesAnstey/esgwrapper.git
cd esgwrapper
python -m pip install -e .
```
Finally, ensure `esgvoc` has the necessary projects and schema versions for all projects to be published to:
```bash
esgvoc use universe@latest cmip7@latest cordex-cmip6@latest cmip6plus@latest
```

⚠️ As of Sep 2026 python3.12 is the latest version on the server, and also is the [minimum python version required by esgvoc](https://esgf.github.io/esgf-vocab/user/introduction.html#requirements).

⚠️ Schema versions can be finicky. Although publishing is supposed to work with `latest`, if it does not then using an earlier schema version may be necessary. `esgvoc list-remote` will list available versions for all projects.


### Workflow

To set up working dirs, starting in your `esgwrapper/` repo dir:
```bash
cd work  # create dir if needed
cp ../config/config-workdirs.yaml .
# edit config-workdirs.yaml as needed
work_dirs_setup
```
This initializes working dirs with names like `cmip7_CMIP_CanESM5-1`.
A work dir contains a `config-datasets.yaml` file that specifies which directories to inventory and keep/exlude filters for publishing datasets.
Example contents:
```yaml
project: cmip7
inventory:  # note, inventory (publish -i) is NOT affected by "keep" or "exclude"
- MIP-DRS7/CMIP7/DAMIP/CCCma/CanESM6-0-MR  # list of paths to inventory can be as granular as you like
keep:
  experiment_id:
  - historical
exclude:
  variable_id:
  - basin
paths:  # all the top-level paths in which to search for datasets
- /space/hall7/sitestore/eccc/crd/cccma/model_output/CMIP7/final  # science
- /CCCMA_NFS/esg/esg_ng  # server
```
The work dir will also have a `mapfiles/` dir to keep all mapfiles, and a `logs/` dir where output from publishing commands will be logged.

⚠️ TODO: document these steps that are run in a work dir:

- `publish -i -b`: generate inventory file `inventory.json`
- `generate_mapfiles datasets.json mapfiles -ce`: check to mapfile existence, then re-run without `-ce` to generate any missing mapfiles (can also run on `inventory.json`) (noting mapfile generation is MUCH faster on science than on the server)
- `sync_to_server.sh`: sync work dirs to server
- `publish -d -c7 -core`: check for core variables to publish (subject to `config-datasets.yaml` filters) and generates `datasets.json`
- `publish -d -c7`: as above but check for *any* variables to publish (subject to `config-datasets.yaml` filters)
- `generate_mapfiles datasets.json mapfiles -ce`: check to mapfile existence before running `publish -p` (if a mapfile doesn't exist then the dataset will be skipped, but it's useful to know before running if there are missing mapfiles)
- `publish -p`: publish the datasets in `datasets.json` (various filters available: `-n` number to try, `-max` max dataset size, `-r` number of retries if first attempt fails, `-dry` to do dry run to show the publishing commands without executing them, etc).

⚠️ The `-c7` option for `publish -d` prevents already-published CMIP7 datasets from being included in `datasets.json`. Attempting to publish datasets that are already published should not break anything (the ESGF index node will reject them) but it's a waste of time.

⚠️ `publish -m` will also generate mapfiles, but using `generate_mapfiles` is a better option.

Logfiles in the work dir's `logs` dir will indicate the results of the various kinds of publishing commands, for example:
```bash
-rw-r--r-- 1 scrd106 eccc_ccrn_shr 5.7M Oct 19 00:39 inventory_2026.10.19_00.30.38_UTC.log
-rw-r--r-- 1 scrd106 eccc_ccrn_shr  61K Oct 19 02:08 datasets_2026.10.19_02.06.32_UTC.log
-rw-r--r-- 1 scrd106 eccc_ccrn_shr  54K Oct 19 04:21 publish_2026.10.19_02.12.17_UTC.log
```

### Further info

General documentation on how to publish to ESGF at CCCma can be [found here](https://gitlab.science.gc.ca/CCCma/cccma_data_publishing/-/blob/master/docs/README_ESGF_publishing.md).
