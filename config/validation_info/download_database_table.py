'''
Query A4D validation database to get validation status of variables.
Author: Kristi Webb

This is required in the env:
    pip install psycopg2-binary

Steps to run it (the activated env must include psycopg2):
    ssh hpcr7-vis6
    source your_env/bin/activate
    python download_database_table.py --database_name CMIP7_CanESM5.1

get_validation_statuses.py call this script to query the database for csv_version = 2.
'''

import argparse
import os

from sqlalchemy import (
    create_engine, 
    text,
    bindparam,
)
import pandas as pd


VALIDATAION_DB_URI_BASE = 'postgresql://scrd115@localhost:44051/'

def get_validation_db_engine( val_database_name ):

    val_db_engine = create_engine( VALIDATAION_DB_URI_BASE + val_database_name )
    # test connection
    with val_db_engine.connect():
        pass
        
    return val_db_engine

def query_db(engine=None, query='', params=None, one=False, conn=None):
    def _query_db(conn, params):
        """
        Execute a SQL query safely, expanding list parameters for IN clauses.

        Args:
            conn: SQLAlchemy connection object.
            query: SQL query string, with named parameters like :param_name
            params: dictionary of parameters

        Returns:
            List of dictionaries (rows)
        """
        params = params or {}

        # Detect list parameters and bind them with expanding=True
        bind_params = []
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                bind_params.append(bindparam(key, expanding=True))

        stmt = text(query)
        if bind_params:
            stmt = stmt.bindparams(*bind_params)
                
        try:
            result = conn.execute(stmt, params)
        except Exception as e:
            query_ = query.replace('\n','')
            raise Exception(f"Failed to _query_db for input query={query_},  params={params}: {e}")
        
        if result.returns_rows:
            rows = result.mappings().all()
            rows = [dict(row) for row in rows]  # Convert RowMapping to dict
            column_keys = list(result.keys())
            if len(column_keys) == 1:
                return [row[column_keys[0]] for row in rows if [column_keys[0]]]
            return rows if not one else rows[0] if rows else None

        return None

    if conn:
        return  _query_db(conn, params)
        
    with engine.connect() as conn_:
        return  _query_db(conn_, params)

def main( database_name, **extras ):

    engine = get_validation_db_engine( database_name )

    # get a list of all model runs used to aggregate variable statuses
    query = "SELECT DISTINCT source_run FROM relation_variable_diagnostics;"
    source_runs = query_db( engine, query )

    if len( source_runs )==1:
        source_run = source_runs[0]

        query = f"""
            SELECT v.uid, v.aggregate_status, dr.cmip7_compound_name, r.source_run, r.diagnostic_config_hash, s.source_filepath 
            FROM relation_variable_diagnostics r
            JOIN latest_data_request dr
                ON r.uid = dr.uid
            LEFT JOIN variable_status v
                ON r.uid = v.uid 
            LEFT JOIN "{source_run}" s
                ON r.uid = v.uid 
                AND r.diagnostic_config_hash = s.diagnostic_config_hash
            ;
        """
        results = query_db( engine, query )
    else:
        raise Exception("Resolving SQL query from multiple source paths not yet configured")


    df = pd.DataFrame(results)

    def parse_value( s ):
        if isinstance(s,str):
            return os.path.basename(os.path.dirname(s)) 
        return s

    df['CMOR_output_version'] = [ parse_value(source_filepath)
                                    for source_filepath in df.source_filepath.values ]

    # Use official source_id's in output file names
    filename_model_name = {
        'CMIP7_CanESM5.1': 'CMIP7_CanESM5-1',
        'CMIP7_CanESM6.0': 'CMIP7_CanESM6-0-MR'
    }
    outfile = f"variable_status_{filename_model_name[database_name]}_v2.csv"
    df.to_csv( outfile, index=False )
    print(f'Saved to: {outfile}')
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=""
    )
    parser.add_argument(
        "--database_name",
        type=str,
        required=True,
        help="Name of validation database",
    )
    args = parser.parse_args()
    main(**vars(args))
