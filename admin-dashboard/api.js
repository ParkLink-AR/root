// ───────────────────────────────────────────────
//  ParkLink Admin Dashboard – data fetching layer
// ───────────────────────────────────────────────

// Wrapper que absorbe errores de red/CORS y devuelve null en vez de romper
async function safeFetch(url, options = {}) {
  try {
    const res = await fetch(url, { ...options, signal: AbortSignal.timeout(5000) });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// Helper: ISO date strings for "N days ago" and "now"
function isoRange(daysAgo) {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - daysAgo);
  return {
    from: start.toISOString(),
    to: end.toISOString(),
  };
}

// ── Payment metrics ───────────────────────────────────────────────────────────

async function fetchPaymentTotal(token) {
  const data = await safeFetch(
    `${CONFIG.PAYMENT_URL}/api/payments/metrics`,
    { headers: authHeaders(token) }
  );
  return data ? parseFloat(data.totalAmount) || 0 : null;
}

async function fetchPaymentByPeriod(token, daysAgo) {
  const { from, to } = isoRange(daysAgo);
  const data = await safeFetch(
    `${CONFIG.PAYMENT_URL}/api/payments/metrics?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { headers: authHeaders(token) }
  );
  return data ? parseFloat(data.totalAmount) || 0 : null;
}

// ── Auth / user metrics ───────────────────────────────────────────────────────

async function fetchUserStats(token) {
  // Endpoint aún no implementado – degradación graceful
  return await safeFetch(
    `${CONFIG.AUTH_URL}/admin/users/stats`,
    { headers: authHeaders(token) }
  );
}

// ── Parking-spot metrics ──────────────────────────────────────────────────────

async function fetchParkingStats(token) {
  // Endpoint aún no implementado – degradación graceful
  return await safeFetch(
    `${CONFIG.PARKING_URL}/admin/parking-spots/stats`,
    { headers: authHeaders(token) }
  );
}

// ── Booking metrics ───────────────────────────────────────────────────────────

async function fetchBookingStats(token) {
  return await safeFetch(
    `${CONFIG.GATEWAY_URL}/api/v1/admin/bookings/stats`,
    { headers: authHeaders(token) }
  );
}

// ── Weekly chart data (last 7 days, one bucket per day) ───────────────────────

async function fetchWeeklyRevenue(token) {
  const days = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
  const buckets = [];
  for (let i = 6; i >= 0; i--) {
    const from = new Date();
    from.setDate(from.getDate() - i);
    from.setHours(0, 0, 0, 0);
    const to = new Date(from);
    to.setHours(23, 59, 59, 999);

    const data = await safeFetch(
      `${CONFIG.PAYMENT_URL}/api/payments/metrics?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`,
      { headers: authHeaders(token) }
    );
    buckets.push({ label: days[from.getDay()], amount: data ? parseFloat(data.totalAmount) || 0 : 0 });
  }
  return buckets;
}

// ── Monthly chart data (last 6 months) ────────────────────────────────────────

async function fetchMonthlyRevenue(token) {
  const monthNames = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const buckets = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date();
    d.setDate(1);
    d.setMonth(d.getMonth() - i);
    const from = new Date(d.getFullYear(), d.getMonth(), 1, 0, 0, 0, 0);
    const to = new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999);

    const data = await safeFetch(
      `${CONFIG.PAYMENT_URL}/api/payments/metrics?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`,
      { headers: authHeaders(token) }
    );
    buckets.push({ label: monthNames[d.getMonth()], amount: data ? parseFloat(data.totalAmount) || 0 : 0 });
  }
  return buckets;
}

// ── Master loader ─────────────────────────────────────────────────────────────

async function loadAllMetrics(token) {
  const [
    paymentTotal,
    paymentWeek,
    paymentMonth,
    userStats,
    parkingStats,
    bookingStats,
    weeklyRevenue,
    monthlyRevenue,
  ] = await Promise.allSettled([
    fetchPaymentTotal(token),
    fetchPaymentByPeriod(token, 7),
    fetchPaymentByPeriod(token, 30),
    fetchUserStats(token),
    fetchParkingStats(token),
    fetchBookingStats(token),
    fetchWeeklyRevenue(token),
    fetchMonthlyRevenue(token),
  ]);

  return {
    paymentTotal: paymentTotal.status === "fulfilled" ? paymentTotal.value : null,
    paymentWeek: paymentWeek.status === "fulfilled" ? paymentWeek.value : null,
    paymentMonth: paymentMonth.status === "fulfilled" ? paymentMonth.value : null,
    userStats: userStats.status === "fulfilled" ? userStats.value : null,
    parkingStats: parkingStats.status === "fulfilled" ? parkingStats.value : null,
    bookingStats: bookingStats.status === "fulfilled" ? bookingStats.value : null,
    weeklyRevenue: weeklyRevenue.status === "fulfilled" ? weeklyRevenue.value : [],
    monthlyRevenue: monthlyRevenue.status === "fulfilled" ? monthlyRevenue.value : [],
  };
}
