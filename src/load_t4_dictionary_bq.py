"""Load the T4 merchant dictionary into BigQuery for crosswalk joins.

The generated SQL (`sql/apply_crosswalk.sql`) joins this table instead of
inlining ~91k UNNEST structs (that query exceeded BigQuery's 1 MB limit).

Usage:
    python src/load_t4_dictionary_bq.py
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd
from google.cloud import bigquery

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV = ROOT / "taxonomy" / "merchant_dictionary.csv"
PROJECT = "raylo-production"
DATASET = "credit_risk_research"
TABLE = "merchant_dictionary_t4"
TABLE_ID = f"{PROJECT}.{DATASET}.{TABLE}"


def main():
    if not CSV.exists():
        raise SystemExit(f"missing {CSV}")
    client = bigquery.Client(project=PROJECT)
    ds_id = f"{PROJECT}.{DATASET}"
    try:
        dataset = client.get_dataset(ds_id)
        print(f"dataset {ds_id} location={dataset.location}")
    except Exception:
        loc = client.get_dataset(f"{PROJECT}.dbt_production").location
        print(f"creating dataset {ds_id} location={loc}", file=sys.stderr)
        dataset = bigquery.Dataset(ds_id)
        dataset.location = loc
        client.create_dataset(dataset, exists_ok=True)

    df = pd.read_csv(CSV, dtype=str).fillna("")
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("normalised_merchant", "STRING"),
            bigquery.SchemaField("detailed_category", "STRING"),
            bigquery.SchemaField("confidence", "STRING"),
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("review_status", "STRING"),
            bigquery.SchemaField("notes", "STRING"),
        ],
    )
    job = client.load_table_from_dataframe(df, TABLE_ID, job_config=job_config)
    job.result()
    table = client.get_table(TABLE_ID)
    print(f"loaded {TABLE_ID}: {table.num_rows:,} rows")


if __name__ == "__main__":
    main()
