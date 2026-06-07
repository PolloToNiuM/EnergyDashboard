import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from energy_ingestion.clients.rte_client import RTEClient
from energy_ingestion.loaders.processed_loader import save_dataframe_parquet
from energy_ingestion.loaders.raw_loader import RawLoader, RawLoaderError
from energy_ingestion.transforms.common import (
    add_standard_columns,
    infer_granularity,
    normalize_timestamps,
    remove_duplicates,
)


ACTUAL_GENERATION_ENDPOINT = (
    "/open_api/actual_generation/v1/actual_generations_per_production_type"
)


def transform_actual_generation(raw_data: dict) -> pd.DataFrame:
    rows = []

    for block in raw_data["actual_generations_per_production_type"]:
        production_type = block.get("production_type") or block.get("type")

        for value in block["values"]:
            rows.append(
                {
                    "timestamp": value["start_date"],
                    "end_date": value["end_date"],
                    "updated_date": value.get("updated_date"),
                    "production_type": production_type,
                    "value": value["value"],
                }
            )

    df = pd.DataFrame(rows)

    df = normalize_timestamps(df)
    df = add_standard_columns(
        df,
        metric="actual_generation_per_production_type",
        granularity=infer_granularity(df, group_column="production_type"),
    )
    df = remove_duplicates(df, subset=["timestamp", "production_type"])

    return df[
        [
            "timestamp",
            "end_date",
            "updated_date",
            "source",
            "metric",
            "production_type",
            "value",
            "unit",
            "zone",
            "granularity",
        ]
    ]
def load_or_fetch_actual_generation_raw() -> dict:
    loader = RawLoader()

    try:
        raw_path = loader.latest_file(
            "rte",
            dataset="actual_generation",
            pattern="*.json",
        )
        print("Raw charge :", raw_path)
        return loader.load_json(raw_path)
    except RawLoaderError:
        print("Aucun raw actual_generation trouve, appel de l'API RTE...")

    with RTEClient.from_env() as client:
        response = client.get_raw(
            ACTUAL_GENERATION_ENDPOINT,
            dataset="actual_generation",
        )
        print("Raw sauvegarde :", response.raw_path)
        return response.json()


if __name__ == "__main__":
    raw_data = load_or_fetch_actual_generation_raw()
    df = transform_actual_generation(raw_data)
    parquet_path = save_dataframe_parquet(df, dataset="actual_generation")

    print(df.head())
    print(df.info())
    print(df["production_type"].nunique())
    print(df[["timestamp", "production_type", "value"]].head())
    print("Parquet sauvegarde :", parquet_path)
