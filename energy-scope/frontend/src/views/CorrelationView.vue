<script setup>
import { computed, onMounted, ref, watch } from "vue";
import DualAxisChart from "../components/charts/DualAxisChart.vue";
import {
  fetchMeasurements,
  syncActualGeneration,
  syncConsumption,
  syncWeather,
} from "../api/measurements";
import {
  formatDateInputValue,
  getSelectedDateRange,
} from "../utils/parisTime";

const comparisons = [
  {
    id: "consumption-temperature",
    label: "Consommation vs temperature",
    heading: "Consommation et temperature moyenne",
    leftName: "Consommation",
    rightName: "Temperature",
    leftUnit: "MW",
    rightUnit: "C",
    leftQuery: {
      metric: "consumption_short_term",
      measurement_type: "REALISED",
    },
    rightQuery: {
      metric: "weather_hourly",
      measurement_type: "temperature_2m",
      zone: "France",
    },
    sync: [syncConsumption, syncWeather],
    kpis: [
      { label: "Conso max", side: "left", aggregate: "max", unit: "MW" },
      { label: "Temp. moyenne", side: "right", aggregate: "avg", unit: "C" },
    ],
  },
  {
    id: "solar-radiation",
    label: "Solaire vs rayonnement",
    heading: "Production solaire et rayonnement",
    leftName: "Solaire",
    rightName: "Rayonnement",
    leftUnit: "MW",
    rightUnit: "W/m2",
    leftQuery: {
      metric: "actual_generation_per_production_type",
      production_type: "SOLAR",
    },
    rightQuery: {
      metric: "weather_hourly",
      measurement_type: "shortwave_radiation",
      zone: "France",
    },
    sync: [syncActualGeneration, syncWeather],
    kpis: [
      { label: "Solaire max", side: "left", aggregate: "max", unit: "MW" },
      { label: "Rayon. moyen", side: "right", aggregate: "avg", unit: "W/m2" },
    ],
  },
  {
    id: "wind-wind-speed",
    label: "Eolien vs vent",
    heading: "Production eolienne et vitesse du vent",
    leftName: "Eolien",
    rightName: "Vent",
    leftUnit: "MW",
    rightUnit: "km/h",
    leftQueries: [
      {
        metric: "actual_generation_per_production_type",
        production_type: "WIND_ONSHORE",
      },
      {
        metric: "actual_generation_per_production_type",
        production_type: "WIND_OFFSHORE",
      },
    ],
    rightQuery: {
      metric: "weather_hourly",
      measurement_type: "wind_speed_100m",
      zone: "France",
    },
    sync: [syncActualGeneration, syncWeather],
    kpis: [
      { label: "Eolien max", side: "left", aggregate: "max", unit: "MW" },
      { label: "Vent moyen", side: "right", aggregate: "avg", unit: "km/h" },
    ],
  },
];

const selectedDate = ref(formatDateInputValue(new Date()));
const maxSelectableDate = formatDateInputValue(new Date());
const selectedComparisonId = ref(comparisons[0].id);
const chartMode = ref("real");
const leftMeasurements = ref([]);
const rightMeasurements = ref([]);
const isLoading = ref(true);
const error = ref("");
const loadingMessage = ref("Chargement des mesures...");

const selectedComparison = computed(
  () => comparisons.find((comparison) => comparison.id === selectedComparisonId.value) ?? comparisons[0],
);

const leftSeries = computed(() => toSeries(leftMeasurements.value));
const rightSeries = computed(() => toSeries(rightMeasurements.value));
const canShowChart = computed(() => leftSeries.value.length > 0 && rightSeries.value.length > 0);

const kpiValues = computed(() =>
  selectedComparison.value.kpis.map((kpi) => {
    const values = (kpi.side === "left" ? leftSeries.value : rightSeries.value).map((point) => point[1]);
    return {
      ...kpi,
      value: aggregateValues(values, kpi.aggregate),
    };
  }),
);

async function loadAnalysis() {
  isLoading.value = true;
  error.value = "";
  loadingMessage.value = "Chargement des mesures...";

  const { startDate, endDate } = getSelectedDateRange(selectedDate.value);

  try {
    leftMeasurements.value = await loadSideMeasurements("left", startDate, endDate);
    rightMeasurements.value = await loadSideMeasurements("right", startDate, endDate);

    if (leftMeasurements.value.length === 0 || rightMeasurements.value.length === 0) {
      loadingMessage.value = "Recuperation des donnees manquantes...";
      await syncSelectedComparison();
      leftMeasurements.value = await loadSideMeasurements("left", startDate, endDate);
      rightMeasurements.value = await loadSideMeasurements("right", startDate, endDate);
    }
  } catch (caughtError) {
    error.value = caughtError.message;
  } finally {
    isLoading.value = false;
  }
}

async function loadSideMeasurements(side, startDate, endDate) {
  const queries = getQueries(side);
  const batches = await Promise.all(
    queries.map((query) =>
      fetchMeasurements({
        ...query,
        start_date: startDate,
        end_date: endDate,
        limit: 5000,
      }),
    ),
  );
  return mergeMeasurements(batches.flat());
}

function getQueries(side) {
  const comparison = selectedComparison.value;
  const pluralKey = side === "left" ? "leftQueries" : "rightQueries";
  const singleKey = side === "left" ? "leftQuery" : "rightQuery";
  return comparison[pluralKey] ?? [comparison[singleKey]];
}

function mergeMeasurements(measurements) {
  const grouped = new Map();

  for (const measurement of measurements) {
    const key = measurement.timestamp;
    grouped.set(key, (grouped.get(key) ?? 0) + Number(measurement.value));
  }

  return Array.from(grouped.entries())
    .map(([timestamp, value]) => ({ timestamp, value }))
    .sort((left, right) => new Date(left.timestamp) - new Date(right.timestamp));
}

function toSeries(measurements) {
  return measurements.map((measurement) => [measurement.timestamp, measurement.value]);
}

async function refreshAnalysis() {
  isLoading.value = true;
  error.value = "";
  loadingMessage.value = "Actualisation des donnees...";

  try {
    await syncSelectedComparison();
    await loadAnalysis();
  } catch (caughtError) {
    error.value = caughtError.message;
    isLoading.value = false;
  }
}

async function syncSelectedComparison() {
  const syncFns = [...new Set(selectedComparison.value.sync)];
  await Promise.all(syncFns.map((syncFn) => syncFn(selectedDate.value)));
}

function aggregateValues(values, aggregate) {
  if (values.length === 0) return null;
  if (aggregate === "max") return Math.max(...values);
  if (aggregate === "min") return Math.min(...values);
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatKpiValue(value, unit) {
  if (value === null) return "-";
  const rounded = unit === "MW" ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded.toLocaleString("fr-FR")} ${unit}`;
}

watch([selectedDate, selectedComparisonId], loadAnalysis);
onMounted(loadAnalysis);
</script>

<template>
  <main class="dashboard-view">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Energy Scope</p>
        <h1>Analyses croisees</h1>
      </div>
      <div class="status-panel">
        <span>Comparaison</span>
        <strong>{{ selectedComparison.label }}</strong>
      </div>
    </header>

    <section class="chart-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Correlation</p>
          <h2>{{ selectedComparison.heading }}</h2>
        </div>
        <div class="chart-actions">
          <label class="date-filter">
            <span>Comparaison</span>
            <select v-model="selectedComparisonId">
              <option
                v-for="comparison in comparisons"
                :key="comparison.id"
                :value="comparison.id"
              >
                {{ comparison.label }}
              </option>
            </select>
          </label>
          <label class="date-filter">
            <span>Date</span>
            <input v-model="selectedDate" type="date" :max="maxSelectableDate" />
          </label>
          <button class="refresh-button" type="button" :disabled="isLoading" @click="refreshAnalysis">
            Actualiser
          </button>
        </div>
      </div>

      <div class="analysis-toolbar">
        <div class="segmented-control" aria-label="Mode d'affichage">
          <button
            type="button"
            :class="{ active: chartMode === 'real' }"
            @click="chartMode = 'real'"
          >
            Valeurs reelles
          </button>
          <button
            type="button"
            :class="{ active: chartMode === 'normalized' }"
            @click="chartMode = 'normalized'"
          >
            Normalise 0-100
          </button>
        </div>
        <div class="kpi-strip">
          <article v-for="kpi in kpiValues" :key="kpi.label" class="kpi-card">
            <span>{{ kpi.label }}</span>
            <strong>{{ formatKpiValue(kpi.value, kpi.unit) }}</strong>
          </article>
        </div>
      </div>

      <div v-if="isLoading" class="state-message">{{ loadingMessage }}</div>
      <div v-else-if="error" class="state-message error">{{ error }}</div>
      <div v-else-if="!canShowChart" class="state-message">
        Donnees insuffisantes pour cette comparaison
      </div>
      <DualAxisChart
        v-else
        :left-series="leftSeries"
        :right-series="rightSeries"
        :selected-date="selectedDate"
        :mode="chartMode"
        :left-name="selectedComparison.leftName"
        :right-name="selectedComparison.rightName"
        :left-unit="selectedComparison.leftUnit"
        :right-unit="selectedComparison.rightUnit"
      />
    </section>
  </main>
</template>
