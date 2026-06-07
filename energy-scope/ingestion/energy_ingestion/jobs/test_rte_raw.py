"""Smoke test for the RTE client and raw data persistence."""

from energy_ingestion.clients.rte_client import RTEClient


def main() -> None:
    endpoint = "/open_api/consumption/v1/short_term"
    params = {
        "start_date": "2026-06-01T00:00:00+02:00",
        "end_date": "2026-06-02T00:00:00+02:00",
    }

    with RTEClient.from_env() as client:
        response = client.get_raw(endpoint, params=params, dataset="consumption")
        raw_data = response.json()

    print("OK - fichier sauvegarde :", response.raw_path)
    print("Metadata :", response.metadata_path)
    print("Status HTTP :", response.status_code)
    print("Dataset :", response.dataset)
    print("Cles recues :", raw_data.keys())


if __name__ == "__main__":
    main()
