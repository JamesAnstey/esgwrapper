
## How to get validation statuses of CMIP7 variables

On science (ECCC HPC) run:
```bash
python get_validation_statuses.py
```
This queries the validation database and writes csv files with statuses for each model in the current directory.
It then reads these files and produces `validation_status.json` which contains the approval status and other metadata of all variables for each model.
It requires `postgresql_export.sh` and `download_validation_files.sh` in the current directory.

To write `validation_status.json` using existing csv files in the current directory, i.e. without querying the database, invoke with the `-ndb` flag.

`validation_status.json` can be used by the publishing software to confirm a varibale is approved before publishing.
Its header has some useful info:
```json
    "Header": {
        "date run": "30 Sep 2026 01:56:53 UTC",
        "models": {
            "CanESM5-1": {
                "provenance file": "variable_status_CMIP7_CanESM5-1.csv",
                "provenance file timestamp": "29 Sep 2026 23:29:35 UTC",
                "no. of variables": 630,
                "no. of variables by status": {
                    "approved": 568,
                    "rejected": 14,
                    "under investigation": 9,
                    "unexamined": 39
                }
            },
```
`date run` indicates when `get_validation_statuses.py` was run.
`provenance file timestamp` indicates when the csv file, `provenance file`, was generated from the database (i.e., when the csv file was last modified; it should not be edited manually).

Information about each variable is stored as follows:
```json
    "model": {
        "CanESM5-1": {
            "aerosol.abs550aer.tavg-u-hxy-u.mon.glb": {
                "aggregate_status": "approved",
                "source_id": "CanESM5-1",
                "cmip7_compound_name": "aerosol.abs550aer.tavg-u-hxy-u.mon.glb",
                "realm": "aerosol",
                "variable_id": "abs550aer",
                "branding_suffix": "tavg-u-hxy-u",
                "frequency": "mon",
                "region": "glb",
                "uid": "19bebf2a-81b1-11e6-92de-ac72891c3257"
            }
```
`aggregate_status` is output from the A4D validation system and indicates if the variable is approved.
If the status is anything other than `"approved"`, the variable should not be published.
