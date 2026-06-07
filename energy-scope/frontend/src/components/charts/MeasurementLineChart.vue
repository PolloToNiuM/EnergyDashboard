<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import {
  formatParisTime,
  getParisDayBounds,
} from "../../utils/parisTime";

const props = defineProps({
  measurements: {
    type: Array,
    required: true,
  },
  selectedDate: {
    type: String,
    required: true,
  },
  zoomYAxis: {
    type: Boolean,
    default: false,
  },
});

const chartEl = ref(null);
let chart = null;

const series = computed(() => {
  const grouped = new Map();

  for (const measurement of props.measurements) {
    const name = measurement.production_type || measurement.measurement_type || measurement.metric;
    if (!grouped.has(name)) {
      grouped.set(name, []);
    }

    grouped.get(name).push([measurement.timestamp, measurement.value]);
  }

  return Array.from(grouped.entries()).map(([name, data]) => ({
    name,
    type: "line",
    showSymbol: false,
    smooth: true,
    lineStyle: { width: 2 },
    data: data.sort((left, right) => new Date(left[0]) - new Date(right[0])),
  }));
});

const yAxisBounds = computed(() => {
  if (!props.zoomYAxis || props.measurements.length === 0) {
    return {};
  }

  const values = props.measurements
    .map((measurement) => Number(measurement.value))
    .filter(Number.isFinite);

  if (values.length === 0) {
    return {};
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const padding = Math.max(range * 0.08, maxValue * 0.01, 100);

  return {
    min: Math.max(0, Math.floor(minValue - padding)),
    max: Math.ceil(maxValue + padding),
    scale: true,
  };
});

function renderChart() {
  if (!chart) return;
  const dayBounds = getParisDayBounds(props.selectedDate);

  chart.setOption(
    {
      color: ["#1f7a5a", "#d77a2d", "#3267b1", "#b2364a", "#718096", "#c8a227"],
      tooltip: {
        trigger: "axis",
        formatter: formatTooltip,
        valueFormatter: (value) => `${Math.round(value).toLocaleString("fr-FR")} MW`,
      },
      legend: {
        type: "scroll",
        top: 0,
        textStyle: { color: "#21312b" },
      },
      grid: {
        top: 56,
        right: 28,
        bottom: 42,
        left: 64,
      },
      xAxis: {
        type: "time",
        min: dayBounds.min,
        max: dayBounds.max,
        axisLine: { lineStyle: { color: "#8da39a" } },
        axisLabel: {
          color: "#546861",
          formatter: formatParisTime,
        },
      },
      yAxis: {
        type: "value",
        name: "MW",
        nameTextStyle: { color: "#546861" },
        splitLine: { lineStyle: { color: "#d9e3df" } },
        axisLabel: { color: "#546861" },
        ...yAxisBounds.value,
      },
      series: series.value,
    },
    { notMerge: true },
  );
}

function formatTooltip(params) {
  if (!params.length) return "";

  const lines = [`<strong>${formatParisTime(params[0].axisValue)}</strong>`];
  for (const param of params) {
    lines.push(
      `${param.marker} ${param.seriesName} <strong>${Math.round(param.value[1]).toLocaleString("fr-FR")} MW</strong>`,
    );
  }
  return lines.join("<br />");
}

function resizeChart() {
  chart?.resize();
}

onMounted(() => {
  chart = echarts.init(chartEl.value);
  renderChart();
  window.addEventListener("resize", resizeChart);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
});

watch(() => [series.value, props.selectedDate, props.zoomYAxis, yAxisBounds.value], renderChart);
</script>

<template>
  <div ref="chartEl" class="measurement-line-chart" />
</template>
