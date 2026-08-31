#!/usr/bin/env bash
# =============================================================================
# ParkLink — Prueba de calidad end-to-end
#
# Uso:
#   ./scripts/qa_test.sh
#
# Pre-requisitos:
#   - Los servicios deben estar corriendo (make up)
#   - jq instalado
#
# Flujo:
#   1.  Crear usuario propietario
#   2.  Crear publicación (lun-vie 8am-8pm, $1500/h)
#   3.  Crear cuenta conductor
#   4.  Ver lista de cocheras → cochera publicada debe aparecer
#   5.  Reservar 9am lunes 1 hora
#   6.  Pago exitoso
#   7.  Verificar que 9am ya no está disponible
#   8.  Reservar 15:00 lunes 1 hora
#   9.  Pago exitoso
#   10. Reservar 8am lunes 1 hora
#   11. Pago exitoso
#   12. Intentar reservar 14:00-16:00 → error de conflicto esperado
# =============================================================================

set -euo pipefail

GATEWAY="http://localhost:8080"
PAYMENT_SVC="http://localhost:8004"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
RESET='\033[0m'

PASS=0
FAIL=0

# Próximo lunes desde hoy
NEXT_MONDAY=$(python3 -c "
from datetime import date, timedelta
today = date.today()
days_ahead = 0 - today.weekday()
if days_ahead <= 0:
    days_ahead += 7
print((today + timedelta(days=days_ahead)).isoformat())
")

step() {
  echo ""
  echo -e "${BOLD}▶ Paso $1: $2${RESET}"
}

ok() {
  echo -e "  ${GREEN}✅ $1${RESET}"
  PASS=$((PASS + 1))
}

fail() {
  echo -e "  ${RED}❌ $1${RESET}"
  FAIL=$((FAIL + 1))
}

assert_status() {
  local label="$1"
  local expected="$2"
  local actual="$3"
  if [ "$actual" = "$expected" ]; then
    ok "$label (HTTP $actual)"
  else
    fail "$label — esperado HTTP $expected, obtenido HTTP $actual"
  fi
}

assert_contains() {
  local label="$1"
  local needle="$2"
  local haystack="$3"
  if echo "$haystack" | grep -q "$needle"; then
    ok "$label"
  else
    fail "$label — no se encontró '$needle' en la respuesta"
  fi
}

assert_not_contains() {
  local label="$1"
  local needle="$2"
  local haystack="$3"
  if echo "$haystack" | grep -q "$needle"; then
    fail "$label — '$needle' todavía aparece en la respuesta (no debería)"
  else
    ok "$label"
  fi
}

echo ""
echo -e "${BOLD}=============================================${RESET}"
echo -e "${BOLD}  ParkLink — Prueba de calidad end-to-end${RESET}"
echo -e "${BOLD}=============================================${RESET}"
echo -e "  Próximo lunes: ${YELLOW}$NEXT_MONDAY${RESET}"

# Timestamp único para evitar conflictos al correr la prueba varias veces
TS=$(date +%s)
OWNER_EMAIL="owner_${TS}@parklink.com"
DRIVER_EMAIL="driver_${TS}@parklink.com"

# ─────────────────────────────────────────────────────────────────────────────
step 1 "Crear usuario propietario ($OWNER_EMAIL)"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$OWNER_EMAIL\",
    \"password\": \"Test1234!\",
    \"first_name\": \"Carlos\",
    \"last_name\": \"Propietario\",
    \"phone\": \"+549111${TS: -7}\",
    \"dni\": \"3${TS: -7}\",
    \"birth_date\": \"1985-06-15\"
  }")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Registro propietario" "201" "$HTTP_STATUS"
OWNER_ID=$(echo "$BODY" | jq -r '.id')
echo -e "  ℹ️  owner_id: $OWNER_ID"

# Login propietario
LOGIN=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$OWNER_EMAIL\", \"password\": \"Test1234!\"}")
OWNER_TOKEN=$(echo "$LOGIN" | jq -r '.access_token')

# ─────────────────────────────────────────────────────────────────────────────
step 2 "Crear publicación cochera (lun-vie 8am-8pm, \$1500/h)"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/parking-spots" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -d '{
    "title": "Cochera QA Test",
    "description": "Cochera creada por prueba automatizada",
    "address": "Av. Corrientes 1234, Buenos Aires",
    "lat": -34.6037,
    "lng": -58.3816,
    "pricePerHour": 1500,
    "covered": true,
    "schedule": [
      {"dayOfWeek": 0, "startHour": 8, "endHour": 20},
      {"dayOfWeek": 1, "startHour": 8, "endHour": 20},
      {"dayOfWeek": 2, "startHour": 8, "endHour": 20},
      {"dayOfWeek": 3, "startHour": 8, "endHour": 20},
      {"dayOfWeek": 4, "startHour": 8, "endHour": 20}
    ]
  }')
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Crear cochera" "201" "$HTTP_STATUS"
SPOT_ID=$(echo "$BODY" | jq -r '.id')
echo -e "  ℹ️  spot_id: $SPOT_ID"

# ─────────────────────────────────────────────────────────────────────────────
step 3 "Crear cuenta conductor ($DRIVER_EMAIL)"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$DRIVER_EMAIL\",
    \"password\": \"Test1234!\",
    \"first_name\": \"Ana\",
    \"last_name\": \"Conductora\",
    \"phone\": \"+549112${TS: -7}\",
    \"dni\": \"4${TS: -7}\",
    \"birth_date\": \"1995-03-20\"
  }")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Registro conductor" "201" "$HTTP_STATUS"
DRIVER_ID=$(echo "$BODY" | jq -r '.id')
echo -e "  ℹ️  driver_id: $DRIVER_ID"

# Login conductor
LOGIN=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$DRIVER_EMAIL\", \"password\": \"Test1234!\"}")
DRIVER_TOKEN=$(echo "$LOGIN" | jq -r '.access_token')

# ─────────────────────────────────────────────────────────────────────────────
step 4 "Ver lista de cocheras — debe aparecer la cochera publicada"

RESPONSE=$(curl -s "http://localhost:8080/parking-spots/search?lat=-34.6037&lng=-58.3816&radius=500")

assert_contains "Cochera QA Test aparece en búsqueda" "Cochera QA Test" "$RESPONSE"
assert_contains "spot_id presente en resultados" "$SPOT_ID" "$RESPONSE"

# ─────────────────────────────────────────────────────────────────────────────
step 5 "Reservar 9am lunes ($NEXT_MONDAY) — 1 hora"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d "{
    \"user_id\": \"$DRIVER_ID\",
    \"start\": \"${NEXT_MONDAY}T09:00:00-03:00\",
    \"end\":   \"${NEXT_MONDAY}T10:00:00-03:00\",
    \"amount\": 1500,
    \"parking_spot\": {
      \"id\": \"$SPOT_ID\",
      \"schedule\": [{\"day_of_week\": 0, \"start_hour\": 8, \"end_hour\": 20}]
    }
  }")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Reserva 9am creada" "201" "$HTTP_STATUS"
assert_contains "Estado PENDING_PAYMENT" "PENDING_PAYMENT" "$BODY"
BOOKING_9AM=$(echo "$BODY" | jq -r '.id')
echo -e "  ℹ️  booking_id: $BOOKING_9AM"

# ─────────────────────────────────────────────────────────────────────────────
step 6 "Pago exitoso — reserva 9am"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$PAYMENT_SVC/api/payments/demo-pay" \
  -H "Content-Type: application/json" \
  -d "{\"bookingId\": \"$BOOKING_9AM\", \"amount\": 1500, \"payerEmail\": \"$DRIVER_EMAIL\"}")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Demo-pay 9am" "201" "$HTTP_STATUS"
assert_contains "Estado approved" "approved" "$BODY"

# ─────────────────────────────────────────────────────────────────────────────
step 7 "Verificar que 9am ya no aparece disponible"

AVAIL=$(curl -s "$GATEWAY/parking-spots/$SPOT_ID/availability?from=$NEXT_MONDAY&to=$(python3 -c "
from datetime import date, timedelta
import sys
d = date.fromisoformat('$NEXT_MONDAY')
print((d + timedelta(days=1)).isoformat())
")")

assert_not_contains "Franja 09:00-10:00 bloqueada" "\"start\":\"${NEXT_MONDAY}T09:00:00-03:00\"" "$AVAIL"
assert_contains "Franja 08:00-09:00 libre" "\"start\":\"${NEXT_MONDAY}T08:00:00-03:00\"" "$AVAIL"

# ─────────────────────────────────────────────────────────────────────────────
step 8 "Reservar 15:00 lunes ($NEXT_MONDAY) — 1 hora"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d "{
    \"user_id\": \"$DRIVER_ID\",
    \"start\": \"${NEXT_MONDAY}T15:00:00-03:00\",
    \"end\":   \"${NEXT_MONDAY}T16:00:00-03:00\",
    \"amount\": 1500,
    \"parking_spot\": {
      \"id\": \"$SPOT_ID\",
      \"schedule\": [{\"day_of_week\": 0, \"start_hour\": 8, \"end_hour\": 20}]
    }
  }")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Reserva 15:00 creada" "201" "$HTTP_STATUS"
BOOKING_15=$(echo "$BODY" | jq -r '.id')
echo -e "  ℹ️  booking_id: $BOOKING_15"

# ─────────────────────────────────────────────────────────────────────────────
step 9 "Pago exitoso — reserva 15:00"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$PAYMENT_SVC/api/payments/demo-pay" \
  -H "Content-Type: application/json" \
  -d "{\"bookingId\": \"$BOOKING_15\", \"amount\": 1500, \"payerEmail\": \"$DRIVER_EMAIL\"}")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Demo-pay 15:00" "201" "$HTTP_STATUS"
assert_contains "Estado approved" "approved" "$BODY"

# ─────────────────────────────────────────────────────────────────────────────
step 10 "Reservar 8am lunes ($NEXT_MONDAY) — 1 hora"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d "{
    \"user_id\": \"$DRIVER_ID\",
    \"start\": \"${NEXT_MONDAY}T08:00:00-03:00\",
    \"end\":   \"${NEXT_MONDAY}T09:00:00-03:00\",
    \"amount\": 1500,
    \"parking_spot\": {
      \"id\": \"$SPOT_ID\",
      \"schedule\": [{\"day_of_week\": 0, \"start_hour\": 8, \"end_hour\": 20}]
    }
  }")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Reserva 8am creada" "201" "$HTTP_STATUS"
BOOKING_8AM=$(echo "$BODY" | jq -r '.id')
echo -e "  ℹ️  booking_id: $BOOKING_8AM"

# ─────────────────────────────────────────────────────────────────────────────
step 11 "Pago exitoso — reserva 8am"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$PAYMENT_SVC/api/payments/demo-pay" \
  -H "Content-Type: application/json" \
  -d "{\"bookingId\": \"$BOOKING_8AM\", \"amount\": 1500, \"payerEmail\": \"$DRIVER_EMAIL\"}")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Demo-pay 8am" "201" "$HTTP_STATUS"
assert_contains "Estado approved" "approved" "$BODY"

# ─────────────────────────────────────────────────────────────────────────────
step 12 "Reservar 14:00-16:00 (2hs) — debe fallar por conflicto con 15:00"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -d "{
    \"user_id\": \"$DRIVER_ID\",
    \"start\": \"${NEXT_MONDAY}T14:00:00-03:00\",
    \"end\":   \"${NEXT_MONDAY}T16:00:00-03:00\",
    \"amount\": 3000,
    \"parking_spot\": {
      \"id\": \"$SPOT_ID\",
      \"schedule\": [{\"day_of_week\": 0, \"start_hour\": 8, \"end_hour\": 20}]
    }
  }")
HTTP_STATUS=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

assert_status "Conflicto de reserva rechazado (409)" "409" "$HTTP_STATUS"
assert_contains "Código BOOKING_CONFLICT" "BOOKING_CONFLICT" "$BODY"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}=============================================${RESET}"
if [ "$FAIL" -eq 0 ]; then
  echo -e "  ${GREEN}${BOLD}RESULTADO: $PASS/$((PASS + FAIL)) checks pasaron ✅${RESET}"
else
  echo -e "  ${RED}${BOLD}RESULTADO: $PASS pasaron / $FAIL fallaron ❌${RESET}"
fi
echo -e "${BOLD}=============================================${RESET}"
echo ""

exit $FAIL
