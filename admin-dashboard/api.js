// ───────────────────────────────────────────────
//  ParkLink Admin Dashboard – data layer
//  Demo mode: returns realistic mock data instantly
//  so the dashboard works without any live backend.
//  Set DEMO_MODE = false to switch to real API calls.
// ───────────────────────────────────────────────

const DEMO_MODE = true;

// ── Helpers ───────────────────────────────────────────────────────────────────

function isoRange(daysAgo) {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - daysAgo);
  return { from: start.toISOString(), to: end.toISOString() };
}

function authHeaders(token) {
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function safeFetch(url, options = {}) {
  try {
    const res = await fetch(url, { ...options, signal: AbortSignal.timeout(5000) });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── Mock data ─────────────────────────────────────────────────────────────────
// Realistic numbers for a growing Argentine parking marketplace.

function buildMockMetrics() {
  // Seed a stable random so numbers don't jump on every refresh
  const seed = Math.floor(Date.now() / 60000); // changes once per minute
  const rnd = (min, max) => min + ((seed * 9301 + 49297) % 233280 / 233280) * (max - min) | 0;

  // Revenue – realistic ARS amounts (~$1 200 – $2 800 per booking)
  const dailyBase   = [8400, 12600, 7200, 18900, 22400, 31500, 14700];
  const monthlyBase = [142000, 198000, 176000, 245000, 312000, 287000];

  // Vary slightly so it looks live
  const weeklyRevenue = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"].map((label, i) => ({
    label,
    amount: dailyBase[i] + rnd(0, 2800),
  }));

  const monthNames = [];
  const monthlyRevenue = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date();
    d.setDate(1);
    d.setMonth(d.getMonth() - i);
    const name = d.toLocaleString("es-AR", { month: "short" });
    monthNames.push(name);
    monthlyRevenue.push({ label: name, amount: monthlyBase[5 - i] + rnd(0, 12000) });
  }

  const paymentTotal = 2_847_320 + rnd(0, 50000);
  const paymentWeek  = weeklyRevenue.reduce((s, b) => s + b.amount, 0);
  const paymentMonth = monthlyRevenue[monthlyRevenue.length - 1].amount
                     + monthlyRevenue[monthlyRevenue.length - 2].amount * 0.6 | 0;

  const userStats = {
    total:         1_284 + rnd(0, 40),
    active:        1_147 + rnd(0, 30),
    suspended:     12,
    deleted:       125,
    new_this_week: 38 + rnd(0, 12),
    new_this_month:142 + rnd(0, 25),
  };

  const parkingStats = {
    total:          387,
    active:         341 + rnd(0, 8),
    paused:         31,
    deleted:        15,
    unique_owners:  198 + rnd(0, 5),
  };

  const bookingStats = {
    total:          8_932 + rnd(0, 120),
    confirmed:      7_104 + rnd(0, 80),
    pending:        214  + rnd(0, 20),
    cancelled:      1_614,
    this_week:      312  + rnd(0, 40),
    this_month:     1_087 + rnd(0, 60),
  };

  return {
    paymentTotal,
    paymentWeek,
    paymentMonth,
    userStats,
    parkingStats,
    bookingStats,
    weeklyRevenue,
    monthlyRevenue,
  };
}

// ── Real API calls (used when DEMO_MODE = false) ──────────────────────────────

async function fetchPaymentTotal(token) {
  const data = await safeFetch(
    `${CONFIG.GATEWAY_URL}/payments/metrics`,
    { headers: authHeaders(token) }
  );
  return data ? parseFloat(data.totalAmount) || 0 : null;
}

async function fetchPaymentByPeriod(token, daysAgo) {
  const { from, to } = isoRange(daysAgo);
  const data = await safeFetch(
    `${CONFIG.GATEWAY_URL}/payments/metrics?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    { headers: authHeaders(token) }
  );
  return data ? parseFloat(data.totalAmount) || 0 : null;
}

async function fetchUserStats(token) {
  return await safeFetch(
    `${CONFIG.AUTH_URL}/admin/users/stats`,
    { headers: authHeaders(token) }
  );
}

async function fetchParkingStats(token) {
  return await safeFetch(
    `${CONFIG.PARKING_URL}/admin/parking-spots/stats`,
    { headers: authHeaders(token) }
  );
}

async function fetchBookingStats(token) {
  return await safeFetch(
    `${CONFIG.GATEWAY_URL}/api/v1/admin/bookings/stats`,
    { headers: authHeaders(token) }
  );
}

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
      `${CONFIG.GATEWAY_URL}/payments/metrics?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`,
      { headers: authHeaders(token) }
    );
    buckets.push({ label: days[from.getDay()], amount: data ? parseFloat(data.totalAmount) || 0 : 0 });
  }
  return buckets;
}

async function fetchMonthlyRevenue(token) {
  const monthNames = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const buckets = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date();
    d.setDate(1);
    d.setMonth(d.getMonth() - i);
    const from = new Date(d.getFullYear(), d.getMonth(), 1, 0, 0, 0, 0);
    const to   = new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999);
    const data = await safeFetch(
      `${CONFIG.GATEWAY_URL}/payments/metrics?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}`,
      { headers: authHeaders(token) }
    );
    buckets.push({ label: monthNames[d.getMonth()], amount: data ? parseFloat(data.totalAmount) || 0 : 0 });
  }
  return buckets;
}

// ── Master loader ─────────────────────────────────────────────────────────────

async function loadAllMetrics(token) {
  if (DEMO_MODE) {
    // Tiny artificial delay so the loading shimmer is visible (~300 ms)
    await new Promise((r) => setTimeout(r, 320));
    return buildMockMetrics();
  }

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
    paymentTotal:   paymentTotal.status   === "fulfilled" ? paymentTotal.value   : null,
    paymentWeek:    paymentWeek.status    === "fulfilled" ? paymentWeek.value    : null,
    paymentMonth:   paymentMonth.status   === "fulfilled" ? paymentMonth.value   : null,
    userStats:      userStats.status      === "fulfilled" ? userStats.value      : null,
    parkingStats:   parkingStats.status   === "fulfilled" ? parkingStats.value   : null,
    bookingStats:   bookingStats.status   === "fulfilled" ? bookingStats.value   : null,
    weeklyRevenue:  weeklyRevenue.status  === "fulfilled" ? weeklyRevenue.value  : [],
    monthlyRevenue: monthlyRevenue.status === "fulfilled" ? monthlyRevenue.value : [],
  };
}
