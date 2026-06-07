<script setup>
import { computed, ref } from "vue";
import DashboardView from "./views/DashboardView.vue";
import ConsumptionView from "./views/ConsumptionView.vue";

const activeView = ref("production");

const tabs = [
  { id: "production", label: "Production" },
  { id: "consumption", label: "Consommation" },
];

const currentView = computed(() =>
  activeView.value === "consumption" ? ConsumptionView : DashboardView,
);
</script>

<template>
  <div>
    <nav class="view-tabs" aria-label="Choix de vue">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="view-tab"
        :class="{ active: activeView === tab.id }"
        type="button"
        @click="activeView = tab.id"
      >
        {{ tab.label }}
      </button>
    </nav>
    <component :is="currentView" />
  </div>
</template>
