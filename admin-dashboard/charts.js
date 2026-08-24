// ───────────────────────────────────────────────
//  ParkLink Admin Dashboard – chart rendering
// ───────────────────────────────────────────────
//  Requires Chart.js loaded before this file.

let weeklyChart = null;
let monthlyChart = null;
let bookingStatusChart = null;
let spotStatusChart = null;

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => ` $${Number(ctx.raw).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { font: { size: 11 }, color: "#6b7280" },
    },
    y: {
      grid: { color: "#f0f2f5" },
      ticks: {
        font: { size: 11 },
        color: "#6b7280",
        callback: (v) => `$${Number(v).toLocaleString("es-AR")}`,
      },
      beginAtZero: true,
    },
  },
};

function buildBarDataset(label, data, color) {
  return {
    label,
    data,
    backgroundColor: color,
    borderRadius: 5,
    borderSkipped: false,
    hoverBackgroundColor: color,
  };
}

// ── Weekly revenue bar chart ──────────────────────────────────────────────────
function renderWeeklyChart(buckets) {
  const ctx = document.getElementById("chart-weekly").getContext("2d");
  if (weeklyChart) weeklyChart.destroy();

  weeklyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: buckets.map((b) => b.label),
      datasets: [buildBarDataset("Ingresos", buckets.map((b) => b.amount), "#3a5bd9")],
    },
    options: {
      ...CHART_DEFAULTS,
      plugins: {
        ...CHART_DEFAULTS.plugins,
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ` $${Number(ctx.raw).toLocaleString("es-AR", { minimumFractionDigits: 2 })} ARS`,
          },
        },
      },
    },
  });
}

// ── Monthly revenue bar chart ─────────────────────────────────────────────────
function renderMonthlyChart(buckets) {
  const ctx = document.getElementById("chart-monthly").getContext("2d");
  if (monthlyChart) monthlyChart.destroy();

  monthlyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: buckets.map((b) => b.label),
      datasets: [buildBarDataset("Ingresos", buckets.map((b) => b.amount), "#7c3aed")],
    },
    options: {
      ...CHART_DEFAULTS,
      plugins: {
        ...CHART_DEFAULTS.plugins,
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ` $${Number(ctx.raw).toLocaleString("es-AR", { minimumFractionDigits: 2 })} ARS`,
          },
        },
      },
    },
  });
}

// ── Booking status doughnut ───────────────────────────────────────────────────
function renderBookingStatusChart(stats) {
  const ctx = document.getElementById("chart-booking-status").getContext("2d");
  if (bookingStatusChart) bookingStatusChart.destroy();

  const confirmed = stats?.confirmed ?? 0;
  const pending   = stats?.pending   ?? 0;
  const cancelled = stats?.cancelled ?? 0;

  bookingStatusChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Confirmadas", "Pendientes", "Canceladas"],
      datasets: [{
        data: [confirmed, pending, cancelled],
        backgroundColor: ["#3a5bd9", "#8d93a5", "#c5cef5"],
        borderWidth: 0,
        hoverOffset: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "70%",
      plugins: {
        legend: {
          display: true,
          position: "right",
          labels: { font: { size: 12 }, color: "#6b7280", boxWidth: 12, padding: 12 },
        },
        tooltip: {
          callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.raw}` },
        },
      },
    },
  });
}

// ── Parking spot status doughnut ──────────────────────────────────────────────
function renderSpotStatusChart(stats) {
  const ctx = document.getElementById("chart-spot-status").getContext("2d");
  if (spotStatusChart) spotStatusChart.destroy();

  const active  = stats?.active  ?? 0;
  const paused  = stats?.paused  ?? 0;
  const deleted = stats?.deleted ?? 0;

  spotStatusChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Activas", "Pausadas", "Eliminadas"],
      datasets: [{
        data: [active, paused, deleted],
        backgroundColor: ["#2563eb", "#ea580c", "#94a3b8"],
        borderWidth: 0,
        hoverOffset: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "70%",
      plugins: {
        legend: {
          display: true,
          position: "right",
          labels: { font: { size: 12 }, color: "#6b7280", boxWidth: 12, padding: 12 },
        },
        tooltip: {
          callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.raw}` },
        },
      },
    },
  });
}

// ── Render all charts from loaded metrics ─────────────────────────────────────
function renderCharts(metrics) {
  if (metrics.weeklyRevenue.length)  renderWeeklyChart(metrics.weeklyRevenue);
  if (metrics.monthlyRevenue.length) renderMonthlyChart(metrics.monthlyRevenue);
  if (metrics.bookingStats)          renderBookingStatusChart(metrics.bookingStats);
  if (metrics.parkingStats)          renderSpotStatusChart(metrics.parkingStats);
}
