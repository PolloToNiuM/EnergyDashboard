<script setup>
import { computed, onMounted, ref, watch } from "vue";
import MeasurementLineChart from "../components/charts/MeasurementLineChart.vue";
import { fetchMeasurements, syncConsumption } from "../api/measurements";
import {
  formatDateInputValue,
  formatParisDateTime,
  getSelectedDateRange,
} from "../utils/parisTime";

const measurements = ref([]);
const isLoading = ref(true);
const error = ref("");
const loadingMessage = ref("Chargement des mesures...");
const maxSelectableDate = formatDateInputValue(new Date());
const selectedDate = ref(maxSelectableDate);

const selectedMeasurementTypes = ref(["REALISED", "ID"]);

const measurementTypeOptions = computed(() => {
  const types = new Set(
    measurements.value
      .map((measurement) => measurement.measurement_type)
      .filter(Boolean),
  );

  return Array.from(types).sort();
});

const filteredMeasurements = computed(() =>
  measurements.value.filter((measurement) =>
    selectedMeasurementTypes.value.includes(measurement.measurement_type),
  ),
);

const latestTimestamp = computed(() => {
  if (measurements.value.length === 0) return "Aucune donnee";

  const latest = measurements.value
    .map((measurement) => new Date(measurement.timestamp))
    .sort((left, right) => right - left)[0];

  return formatParisDateTime(latest);
});

async function loadMeasurements() {
  isLoading.value = true;
  error.value = "";
  loadingMessage.value = "Chargement des mesures...";

  const { startDate, endDate } = getSelectedDateRange(selectedDate.value);

  try {
    measurements.value = await fetchMeasurements({
      metric: "consumption_short_term",
      start_date: startDate,
      end_date: endDate,
      limit: 5000,
    });

    if (measurements.value.length === 0) {
      loadingMessage.value = "Recuperation des donnees RTE...";
      await syncConsumption(selectedDate.value);
      measurements.value = await fetchMeasurements({
        metric: "consumption_short_term",
        start_date: startDate,
        end_date: endDate,
        limit: 5000,
      });
    }

    keepSelectedTypesInData();
  } catch (caughtError) {
    error.value = caughtError.message;
  } finally {
    isLoading.value = false;
  }
}

async function refreshMeasurements() {
  isLoading.value = true;
  error.value = "";
  loadingMessage.value = "Actualisation des donnees RTE...";

  try {
    await syncConsumption(selectedDate.value);
    await loadMeasurements();
  } catch (caughtError) {
    error.value = caughtError.message;
    isLoading.value = false;
  }
}

function keepSelectedTypesInData() {
  const availableTypes = measurementTypeOptions.value;
  if (availableTypes.length === 0) return;

  selectedMeasurementTypes.value = selectedMeasurementTypes.value.filter((type) =>
    availableTypes.includes(type),
  );

  if (selectedMeasurementTypes.value.length === 0) {
    selectedMeasurementTypes.value = [availableTypes[0]];
  }
}

onMounted(loadMeasurements);
watch(selectedDate, loadMeasurements);
</script>

<template>
  <main class="dashboard-view">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Energy Scope</p>
        <h1>Consommation electrique RTE</h1>
      </div>
      <div class="status-panel">
        <span>Dernier point</span>
        <strong>{{ latestTimestamp }}</strong>
      </div>
    </header>

    <section class="chart-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Consumption</p>
          <h2>Consommation court terme</h2>
        </div>
        <div class="chart-actions">
          <label class="date-filter">
            <span>Date</span>
            <input v-model="selectedDate" type="date" :max="maxSelectableDate" />
          </label>
          <button class="refresh-button" type="button" :disabled="isLoading" @click="refreshMeasurements">
            Actualiser
          </button>
          <span class="record-count">{{ filteredMeasurements.length }} mesures</span>
        </div>
      </div>

      <div class="energy-filters" aria-label="Filtres consommation">
        <label
          v-for="measurementType in measurementTypeOptions"
          :key="measurementType"
          class="energy-filter"
        >
          <input
            v-model="selectedMeasurementTypes"
            type="checkbox"
            :value="measurementType"
          />
          <span>{{ measurementType }}</span>
        </label>
      </div>

      <div v-if="isLoading" class="state-message">{{ loadingMessage }}</div>
      <div v-else-if="error" class="state-message error">{{ error }}</div>
      <div v-else-if="filteredMeasurements.length === 0" class="state-message">
        Aucune mesure pour cette date
      </div>
      <MeasurementLineChart
        v-else
        :measurements="filteredMeasurements"
        :selected-date="selectedDate"
        zoom-y-axis
      />
    </section>
  </main>
</template>
