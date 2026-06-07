<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { fetchDataQuality } from "../api/measurements";

const datasets = [
  {
    id: "production",
    label: "Production",
    description: "Actual generation RTE par filiere",
  },
  {
    id: "consumption",
    label: "Consommation",
    description: "Consommation court terme RTE",
  },
  {
    id: "weather",
    label: "Weather",
    description: "Moyennes Open-Meteo France",
  },
];

const selectedDataset = ref("production");
const summary = ref(null);
const isLoading = ref(true);
const error = ref("");

const selectedDatasetLabel = computed(
  () => datasets.find((dataset) => dataset.id === selectedDataset.value)?.label ?? "",
);

const failingChecks = computed(() =>
  summary.value?.checks.filter((check) => !check.passed) ?? [],
);

async function loadQuality() {
  isLoading.value = true;
  error.value = "";

  try {
    summary.value = await fetchDataQuality(selectedDataset.value);
  } catch (caughtError) {
    error.value = caughtError.message;
  } finally {
    isLoading.value = false;
  }
}

function formatScore(score) {
  return `${Number(score ?? 0).toLocaleString("fr-FR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} %`;
}

onMounted(loadQuality);
watch(selectedDataset, loadQuality);
</script>

<template>
  <main class="dashboard-view">
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">Data quality</p>
        <h1>Controle qualite des donnees</h1>
      </div>
      <div class="status-panel" :class="{ success: summary?.passed, danger: summary && !summary.passed }">
        <span>Etat</span>
        <strong>{{ summary?.passed ? "OK" : "A verifier" }}</strong>
      </div>
    </header>

    <section class="chart-section quality-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Checks</p>
          <h2>{{ selectedDatasetLabel }}</h2>
        </div>
        <div class="chart-actions">
          <label class="date-filter">
            <span>Dataset</span>
            <select v-model="selectedDataset">
              <option
                v-for="dataset in datasets"
                :key="dataset.id"
                :value="dataset.id"
              >
                {{ dataset.label }}
              </option>
            </select>
          </label>
          <button class="refresh-button" type="button" :disabled="isLoading" @click="loadQuality">
            Checker
          </button>
        </div>
      </div>

      <div class="dataset-selector" aria-label="Selection dataset qualite">
        <button
          v-for="dataset in datasets"
          :key="dataset.id"
          type="button"
          :class="{ active: selectedDataset === dataset.id }"
          @click="selectedDataset = dataset.id"
        >
          <span>{{ dataset.label }}</span>
          <small>{{ dataset.description }}</small>
        </button>
      </div>

      <div v-if="isLoading" class="state-message">Controle qualite en cours...</div>
      <div v-else-if="error" class="state-message error">{{ error }}</div>
      <div v-else-if="summary" class="quality-content">
        <div class="quality-overview">
          <article class="quality-card">
            <span>Score qualite</span>
            <strong>{{ formatScore(summary.score) }}</strong>
          </article>
          <article class="quality-card">
            <span>Lignes controlees</span>
            <strong>{{ summary.total_rows.toLocaleString("fr-FR") }}</strong>
          </article>
          <article class="quality-card">
            <span>Metric</span>
            <strong>{{ summary.metric }}</strong>
          </article>
          <article class="quality-card">
            <span>Alertes</span>
            <strong>{{ failingChecks.length }}</strong>
          </article>
        </div>

        <div class="quality-checks">
          <article
            v-for="check in summary.checks"
            :key="check.name"
            class="quality-check"
            :class="{ failed: !check.passed }"
          >
            <div>
              <span class="quality-dot" aria-hidden="true"></span>
              <strong>{{ check.label }}</strong>
            </div>
            <span>{{ check.invalid_count.toLocaleString("fr-FR") }} invalides</span>
          </article>
        </div>
      </div>
    </section>
  </main>
</template>
