# ParkLink Admin Dashboard

Panel de administración web para el ecosistema ParkLink. Muestra métricas de facturación, usuarios, cocheras, reservas y estado de los microservicios en tiempo real.

## Estructura

```
admin-dashboard/
├── index.html    – Página principal (SPA multi-panel)
├── styles.css    – Estilos (sin dependencias externas)
├── config.js     – URLs de los servicios y token de admin
├── api.js        – Capa de fetching hacia los microservicios
└── charts.js     – Renderizado de gráficos (Chart.js)
```

## Cómo usarlo

### 1. Con los servicios corriendo (docker compose)

```bash
# Desde la raíz del monorepo
docker compose up --build

# Abrir el dashboard
open admin-dashboard/index.html
```

El dashboard llama directamente a los servicios (CORS debe estar habilitado) o al gateway en `:8080`.

### 2. JWT de administrador

El endpoint `GET /api/payments/metrics` del payment-service requiere un token con claim `role: "admin"` (ver [`payment-service/src/security.js`](../payment-service/src/security.js)).

Podés pegar el token directamente en el campo del topbar del dashboard, o hardcodearlo en [`config.js`](./config.js):

```js
ADMIN_TOKEN: "eyJ...",
```

### 3. Endpoints esperados

| Servicio | Endpoint | Estado |
|---|---|---|
| payment-service | `GET /api/payments/metrics` | ✅ Implementado |
| payment-service | `GET /api/payments/metrics?from=&to=` | ✅ Implementado |
| auth-service | `GET /admin/users/stats` | 🔲 Pendiente |
| parking-service | `GET /admin/parking-spots/stats` | 🔲 Pendiente |
| booking-service | `GET /api/v1/admin/bookings/stats` | 🔲 Pendiente |

El dashboard degrada graciosamente cuando un endpoint no existe: muestra `–` en lugar del número y oculta la alerta cuando los datos llegan.

### Respuestas esperadas (para futura implementación)

```json
// GET /admin/users/stats
{
  "total": 500,
  "active": 480,
  "suspended": 15,
  "deleted": 5,
  "new_this_week": 23,
  "new_this_month": 87
}

// GET /admin/parking-spots/stats
{
  "total": 120,
  "active": 95,
  "paused": 20,
  "deleted": 5,
  "unique_owners": 68
}

// GET /api/v1/admin/bookings/stats
{
  "total": 3400,
  "confirmed": 2800,
  "pending": 200,
  "cancelled": 400,
  "this_week": 45,
  "this_month": 180
}
```

## Paneles disponibles

| Panel | Contenido |
|---|---|
| **Resumen** | KPIs de facturación + usuarios + cocheras + reservas + 2 gráficos rápidos |
| **Ingresos** | Histórico, semanal, mensual + gráficos de barras diario y mensual |
| **Usuarios** | Total, activos, suspendidos, eliminados, nuevos por período |
| **Cocheras** | Total, activas, pausadas, eliminadas, propietarios únicos + doughnut |
| **Reservas** | Total, confirmadas, pendientes, canceladas + doughnut de estados |
| **Estado de Servicios** | Ping en tiempo real a los 4 microservicios + tabla de latencia |

## Auto-refresh

El dashboard se actualiza automáticamente cada **60 segundos**.
