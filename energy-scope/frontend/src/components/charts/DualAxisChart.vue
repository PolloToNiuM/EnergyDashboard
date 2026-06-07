<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import { formatParisTime, getParisDayBounds } from "../../utils/parisTime";

const props = defineProps({
  leftSeries: {
    type: Array,
    required: true,
  },
  rightSeries: {
    type: Array,
    required: true,
  },
  selectedDate: {
    type: String,
    required: true,
  },
  mode: {
    type: String,
    default: "real",
  },
  leftName: {
    type: String,
    default: "Serie A",
  },
  rightName: {
    type: String,
    default: "Serie B",
  },
  leftUnit: {
    type: String,
    default: "MW",
  },
  rightUnit: {
    type: String,
    default: "C",
  },
});

const chartEl = ref(null);
let chart = null;

const normalizedMode = computed(() => props.mode === "normalized");

const chartSeries = computed(() => {
  const leftData = normalizedMode.value ? normalizeSeries(props.leftSeries) : props.leftSeries;
  const rightData = normalizedMode.value ? normalizeSeries(props.rightSeries) : props.rightSeries;

  return [
    {
      name: props.leftName,
      type: "line",
      yAxisIndex: 0,
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 2.5 },
      data: leftData,
    },
    {
      name: props.rightName,
      type: "line",
      yAxisIndex: normalizedMode.value ? 0 : 1,
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 2.5 },
      data: rightData,
    },
  ];
});

function renderChart() {
  if (!chart) return;
  const dayBounds = getParisDayBounds(props.selectedDate);
  const yAxes = normalizedMode.value ? normalizedAxes() : realValueAxes();

  chart.setOption(
    {
      color: ["#3267b1", "#c45f37"],
      tooltip: {
        trigger: "axis",
        formatter: formatTooltip,
      },
      legend: {
        top: 0,
        textStyle: { color: "#21312b" },
      },
      grid: {
        top: 58,
        right: normalizedMode.value ? 34 : 68,
        bottom: 42,
        left: 72,
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
      yAxis: yAxes,
      series: chartSeries.value,
    },
    { notMerge: true },
  );
}

function realValueAxes() {
  return [
    {
      type: "value",
      name: props.leftUnit,
      scale: true,
      nameTextStyle: { color: "#546861" },
      splitLine: { lineStyle: { color: "#d9e3df" } },
      axisLabel: { color: "#546861" },
    },
    {
      type: "value",
      name: props.rightUnit,
      scale: true,
      nameTextStyle: { color: "#546861" },
      axisLabel: { color: "#546861" },
    },
  ];
}

function normalizedAxes() {
  return [
    {
      type: "value",
      name: "0-100",
      min: 0,
      max: 100,
      nameTextStyle: { color: "#546861" },
      splitLine: { lineStyle: { color: "#d9e3df" } },
      axisLabel: { color: "#546861" },
    },
  ];
}

function normalizeSeries(series) {
  const values = series.map((point) => Number(point[1])).filter(Number.isFinite);
  if (values.length === 0) return [];

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;

  return series.map(([timestamp, value]) => [
    timestamp,
    range === 0 ? 50 : ((Number(value) - min) / range) * 100,
  ]);
}

function formatTooltip(params) {
  if (!params.length) return "";

  const lines = [`<strong>${formatParisTime(params[0].axisValue)}</strong>`];
  for (const param of params) {
    const unit = normalizedMode.value
      ? "0-100"
      : param.seriesName === props.leftName
        ? props.leftUnit
        : props.rightUnit;
    lines.push(
      `${param.marker} ${param.seriesName} <strong>${formatValue(param.value[1], unit)}</strong>`,
    );
  }
  return lines.join("<br />");
}

function formatValue(value, unit) {
  const rounded = unit === "0-100" ? Math.round(value) : Math.round(value * 10) / 10;
  return `${rounded.toLocaleString("fr-FR")} ${unit}`;
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

watch(
  () => [
    props.leftSeries,
    props.rightSeries,
    props.selectedDate,
    props.mode,
    props.leftName,
    props.rightName,
  ],
  renderChart,
);
</script>

<template>
  <div ref="chartEl" class="measurement-line-chart" />
</template>
