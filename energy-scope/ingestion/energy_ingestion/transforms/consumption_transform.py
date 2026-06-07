import json
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from energy_ingestion.transforms.common import (
    add_standard_columns,
    normalize_timestamps,
    remove_duplicates,
)
from energy_ingestion.loaders.processed_loader import save_dataframe_parquet


CONSUMPTION_ENDPOINT = "/open_api/consumption/v1/short_term"

def transform_consumption(raw_data: dict) -> pd.DataFrame:
    rows = []

    for block in raw_data["short_term"]:
        for value in block["values"]:
            rows.append({
                "type": block["type"],
                "timestamp": value["start_date"],
                "end_date": value["end_date"],
                "updated_date": value["updated_date"],
                "value": value["value"],
            })

    df = pd.DataFrame(rows)

    df = normalize_timestamps(df)
    df = add_standard_columns(
        df,
        metric="consumption_short_term",
        granularity="15min",
    )
    df = remove_duplicates(df, subset=["timestamp", "type"])

    return df[
        [
            "timestamp",
            "end_date",
            "updated_date",
            "source",
            "metric",
            "type",
            "value",
            "unit",
            "zone",
            "granularity",
        ]
    ]


if __name__ == "__main__":
    with open(
        "energy-scope/data/raw/rte/consumption/year=2026/month=06/day=03/20260603T191705297870Z_open_api_consumption_v1_short_term_3534497b826f4b35.json",
        "r",
        encoding="utf-8",
    ) as f:
        raw_data = json.load(f)

    df = transform_consumption(raw_data)
    parquet_path = save_dataframe_parquet(df, dataset="consumption")

    print(df.head())
    print(df.info())
    print(df["type"].unique())
    print(df[["value", "type"]].head())
    print("Parquet sauvegarde :", parquet_path)
