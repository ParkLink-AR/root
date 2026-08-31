// ParkLink Admin Dashboard – service endpoints
// Local (docker compose): gateway en :8080, resto de servicios en sus
// puertos de siempre. Deployado en Render (ver /render.yaml en la raíz del
// monorepo): cada servicio es su propio Web Service en *.onrender.com.
// Detecta el entorno por hostname así el mismo archivo sirve para los dos
// casos sin build step.
const IS_LOCAL = ["localhost", "127.0.0.1", ""].includes(window.location.hostname);

const CONFIG = IS_LOCAL
  ? {
      // Gateway (proxy hacia todos los servicios internos)
      GATEWAY_URL: "http://localhost:8080",

      // Auth service – FastAPI en :8000, health en /auth/login (no existe /health propio)
      AUTH_URL: "http://localhost:8000",
      AUTH_HEALTH: "/auth/register",   // ruta que devuelve 405/422 = servicio vivo

      // Payment service – Express en :8004
      PAYMENT_URL: "http://localhost:8004",
      PAYMENT_HEALTH: "/health",

      // Parking service – NestJS en :3001, no tiene /health propio
      PARKING_URL: "http://localhost:3001",
      PARKING_HEALTH: "/parking-spots/search?lat=-34.6037&lng=-58.3816&radius=100",

      GATEWAY_HEALTH: "/health",
    }
  : {
      // Nombres de servicio fijados en /render.yaml. Si Render les asignó un
      // sufijo distinto (por colisión de nombre), actualizá estas 4 URLs con
      // las reales de tu dashboard de Render.
      GATEWAY_URL: "https://parklink-gateway.onrender.com",

      AUTH_URL: "https://parklink-auth-service.onrender.com",
      AUTH_HEALTH: "/auth/register",

      // OJO: payment-service no manda header Access-Control-Allow-Origin hoy
      // (ver payment-service/src/app.js) -- este fetch cross-origin va a
      // fallar en el navegador hasta que se le agregue CORS a ese servicio.
      PAYMENT_URL: "https://parklink-payment-service.onrender.com",
      PAYMENT_HEALTH: "/health",

      PARKING_URL: "https://parklink-parking-service.onrender.com",
      PARKING_HEALTH: "/parking-spots/search?lat=-34.6037&lng=-58.3816&radius=100",

      GATEWAY_HEALTH: "/health",
    };

// Admin JWT – pegarlo en el topbar o hardcodearlo acá.
// Debe tener claim role:"admin" (ver payment-service/src/security.js).
CONFIG.ADMIN_TOKEN = "";
