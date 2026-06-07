"""Load transformed actual generation data into PostgreSQL."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from energy_ingestion.loaders.postgres_loader import insert_energy_measurements
from energy_ingestion.transforms.actual_generation_transform import (
    load_or_fetch_actual_generation_raw,
    transform_actual_generation,
)


def main() -> None:
    raw_data = load_or_fetch_actual_generation_raw()
    df = transform_actual_generation(raw_data)
    inserted_count = insert_energy_measurements(df)

    print("OK - lignes inserees :", inserted_count)


if __name__ == "__main__":
    main()
