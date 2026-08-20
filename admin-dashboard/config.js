// ParkLink Admin Dashboard – service endpoints
// When running locally via docker compose, the gateway listens on :8080.
// Override any URL to point directly to a service (useful for dev without docker).
const CONFIG = {
  // Gateway (proxy hacia todos los servicios internos)
  GATEWAY_URL: "http://localhost:8080",

  // Auth service – FastAPI en :8000, health en /auth/login (no existe /health propio)
  AUTH_URL: "http://localhost:8000",
  AUTH_HEALTH: "/auth/register",   // ruta que devuelve 405/422 = servicio vivo

  // Payment service – Express en :8004, CORS abierto (access-control-allow-origin: *)
  PAYMENT_URL: "http://localhost:8004",
  PAYMENT_HEALTH: "/health",

  // Parking service – NestJS en :3001, no tiene /health propio
  PARKING_URL: "http://localhost:3001",
  PARKING_HEALTH: "/parking-spots/search?lat=-34.6037&lng=-58.3816&radius=100",

  // Gateway health
  GATEWAY_HEALTH: "/health",

  // Admin JWT – pegarlo en el topbar o hardcodearlo acá.
  // Debe tener claim role:"admin" (ver payment-service/src/security.js).
  ADMIN_TOKEN: "",
};
