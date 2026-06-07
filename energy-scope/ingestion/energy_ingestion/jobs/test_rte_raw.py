"""Smoke test for the RTE client and raw data persistence."""

import logging

from energy_ingestion.clients.rte_client import RTEClient
from energy_ingestion.logging import configure_logging


logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    endpoint = "/open_api/consumption/v1/short_term"
    params = {
        "start_date": "2026-06-01T00:00:00+02:00",
        "end_date": "2026-06-02T00:00:00+02:00",
    }

    logger.info("rte_raw_smoke_test_started endpoint=%s params=%s", endpoint, params)
    with RTEClient.from_env() as client:
        response = client.get_raw(endpoint, params=params, dataset="consumption")
        raw_data = response.json()
    logger.info(
        "rte_raw_smoke_test_finished status_code=%s raw_path=%s",
        response.status_code,
        response.raw_path,
    )

    print("OK - fichier sauvegarde :", response.raw_path)
    print("Metadata :", response.metadata_path)
    print("Status HTTP :", response.status_code)
    print("Dataset :", response.dataset)
    print("Cles recues :", raw_data.keys())


if __name__ == "__main__":
    main()
