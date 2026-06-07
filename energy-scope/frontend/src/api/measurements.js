const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchMeasurements(params = {}) {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.set(key, value);
    }
  }

  const response = await fetch(`${API_BASE_URL}/measurements?${searchParams}`);

  if (!response.ok) {
    throw new Error(`Unable to fetch measurements: ${response.status}`);
  }

  return response.json();
}

export async function syncActualGeneration(date) {
  const searchParams = new URLSearchParams({ date });
  const response = await fetch(
    `${API_BASE_URL}/measurements/sync/actual-generation?${searchParams}`,
    { method: "POST" },
  );

  if (!response.ok) {
    throw new Error(`Unable to sync actual generation: ${response.status}`);
  }

  return response.json();
}

export async function syncConsumption(date) {
  const searchParams = new URLSearchParams({ date });
  const response = await fetch(
    `${API_BASE_URL}/measurements/sync/consumption?${searchParams}`,
    { method: "POST" },
  );

  if (!response.ok) {
    throw new Error(`Unable to sync consumption: ${response.status}`);
  }

  return response.json();
}
