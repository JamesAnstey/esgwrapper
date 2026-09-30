
# port of the validation database cluster
export PGPORT=44051

psql -p $PGPORT -U scrd115 -d CMIP7_CanESM5.1 \
  -c "\copy (
    SELECT
      v.uid,
      dr.cmip7_compound_name,
      v.aggregate_status
    FROM variable_status v
    JOIN latest_data_request dr
      ON v.uid = dr.uid
  ) TO 'variable_status_CMIP7_CanESM5-1.csv' WITH CSV HEADER"

psql -p $PGPORT -U scrd115 -d CMIP7_CanESM6.0 \
  -c "\copy (
    SELECT
      v.uid,
      dr.cmip7_compound_name,
      v.aggregate_status
    FROM variable_status v
    JOIN latest_data_request dr
      ON v.uid = dr.uid
  ) TO 'variable_status_CMIP7_CanESM6-0-MR.csv' WITH CSV HEADER"
