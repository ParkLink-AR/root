# ParkLink AR - root

Este es el repositorio raíz de ParkLink. Contiene la configuración global para levantar el entorno local (Docker Compose + Makefile) y agrupa todos los microservicios del sistema usando Git Submodules.

---

## Servicios

| Servicio | Puerto (host) | Submódulo | ¿Está en `docker compose up`? |
|---|---|---|---|
| `gateway` | 8080 | [gateway](https://github.com/ParkLink-AR/gateway) | Sí |
| `auth-service` | 8000 | [auth-service](https://github.com/ParkLink-AR/auth-service) | Sí |
| `parking-service` | 3001 | [parking-service](https://github.com/ParkLink-AR/parking-service) | Sí |
| `payment-service` | 8004 | [payment-service](https://github.com/ParkLink-AR/payment-service) | Sí |
| `booking-service` | 8082 | [booking-service](https://github.com/ParkLink-AR/booking-service) | Sí |
| `mobile` (app Expo) | 8081 por defecto (lo elige Expo) | [mobile](https://github.com/ParkLink-AR/mobile) | No, se corre aparte (ver [Conectar la app mobile](#conectar-la-app-mobile)) |
| `notifications-service` | — (interno) | [notifications-service](https://github.com/ParkLink-AR/notifications-service) | Sí — consume `booking.*` de RabbitMQ y manda las push por FCM (ver [Push notifications](#push-notifications)) |

Todo pasa por el **gateway** (puerto 8080): mobile y cualquier cliente externo le pegan a él, nunca directo a un microservicio. El gateway verifica el JWT y reenvía la request al servicio correspondiente (agregando el header `x-user-id`).

---

## Cómo empezar (primer clonado)

Si es la primera vez que te bajás el proyecto, no uses el `git clone` común porque te van a quedar las carpetas de los servicios vacías.

Tenés que clonar la raíz y descargar el código de los submódulos todo junto con este comando:

```bash
git clone --recurse-submodules git@github.com:ParkLink-AR/root.git
```

---

## Levantar el entorno local

### 1. Configurar las variables de entorno

```bash
make env    # crea <servicio>/.env desde su .env.example en cada microservicio (fuera de git)
```

Cada microservicio lee sus claves de su propio `.env`; el `.env` de root solo tiene los tokens de los túneles de Cloudflare (`make online`). Con los `.env` tal cual vienen (todo vacío/con defaults de desarrollo) el sistema **ya funciona**: los servicios que necesitan una API key externa (email, SMS, Mercado Pago) caen a un modo "dev" que loguea lo que haría en vez de fallar. Ver [Variables de entorno / API keys](#variables-de-entorno--api-keys) para el detalle de cada una y cuándo hace falta completarla de verdad.

### 2. Docker

Necesitás Docker (con Compose) corriendo. Después, desde la raíz:

```bash
make up      # equivalente a: docker compose up --build --remove-orphans
```

`make up` corre **en primer plano**, mostrando los logs de todos los servicios en la terminal (no queda en background) — cortalo con `Ctrl+C`. Es la forma más simple de ver, por ejemplo, el código de verificación de 6 dígitos que loguea `auth-service` cuando no hay `BREVO_API_KEY`/Twilio configurados.

Otros comandos del `Makefile`:

```bash
make down    # docker compose down -- baja los contenedores, conserva los volúmenes (DB, avatares)
make clean   # docker compose down -v -- baja los contenedores Y BORRA los volúmenes (DB de cero, se pierden las fotos de perfil subidas)
```

Usá `make clean` cuando quieras arrancar con una base de datos completamente limpia (por ejemplo, después de bajar un submódulo con un cambio de modelo/schema — acá **no se usan migraciones incrementales**, cada servicio recrea su esquema completo desde los modelos actuales al arrancar, así que una DB vieja con columnas de menos puede romper).

### 3. Cargar cuentas de prueba

Después de levantar el entorno por primera vez (o después de un `make clean`), inyectá las cuentas demo con:

```bash
docker exec -i pll-db-auth-1 psql \
    -U parklink_auth -d parklink_auth_db \
    < auth-service/scripts/seed_users.sql
```

Esto inserta (o deja pasar si ya existen) las siguientes cuentas con email ya verificado:

| Email | Contraseña | Rol sugerido |
|---|---|---|
| `conductor@parklink.com` | `Conductor1!` | Conductor (driver) |
| `propietario@parklink.com` | `Propietario1!` | Propietario (owner) |
| `admin@parklink.com` | `Admin1!` | Admin / testing general |

> **Nota:** estas cuentas son solo para desarrollo local. No las uses en un entorno accesible desde internet.

### 4. Verificar que levantó todo

```bash
docker compose ps
curl http://localhost:8080/health   # el gateway responde qué servicios tiene configurados y si RabbitMQ conectó
```

`auth-service` (y el propio `gateway`) además exponen su `/livez`/`/readyz` directo, sin pasar por el proxy: `curl http://localhost:8000/livez`.

---

## Conectar la app mobile

`mobile` es una app Expo, no está en el `docker compose` de la raíz — se corre aparte.

> ⚠️ **Importante:** todos los comandos de la app mobile **deben correr desde la carpeta `mobile/`**, no desde la raíz del repo. Si corrés `npx expo start` desde la raíz, Metro resuelve las rutas mal y Expo Go devuelve un error 404 al intentar cargar la app.

```bash
cd mobile                          # <-- imprescindible, no correr desde la raíz
cp .env.example .env               # ya trae EXPO_PUBLIC_API_URL=http://localhost:8080
npm install
npx expo start
```

`EXPO_PUBLIC_API_URL` tiene que apuntar al **gateway** (no a un microservicio directo). El valor por default (`http://localhost:8080`) funciona tal cual para web y simulador iOS corriendo en la misma máquina que `docker compose`. Para emulador Android usá `http://10.0.2.2:8080`; para un dispositivo físico, la IP LAN de la máquina que corre Docker (ej. `http://192.168.1.50:8080`), con el celular en la misma red — `make local` la pone sola. El resto de las variables está en `mobile/.env.example`.

Para push notifications (development build, no Expo Go) usá `npx expo run:android` / `npx expo run:ios` en vez de `npx expo start` — ver [Push notifications](#push-notifications).

---

## Push notifications

`notifications-service` consume del bus RabbitMQ y manda dos push por FCM:

| Evento (lo publica `booking-service`) | Push a | Título |
|---|---|---|
| `booking.pending_approval` — se pagó, falta que el dueño confirme | **propietario** | 🔔 Tenés una reserva para confirmar |
| `booking.confirmed` — el dueño aprobó (o la cochera es instant-booking) | **conductor** | ✅ ¡Reserva confirmada! |

### Credenciales de Firebase (proyecto `parklink-app`)

- `notifications-service/secrets/firebase-service-account.json` (fuera de git) — se montea en el contenedor de notifications-service. Bajala de Firebase Console → Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada. Sin el archivo, o con `FIREBASE_CREDENTIALS_PATH=` (vacío) en el `.env`, queda en log-only.
- `mobile/google-services.json` (Android) y `mobile/GoogleService-Info.plist` (iOS) — para que el build compile sin bajar nada.

> ⚠️ Si estos repos se hacen públicos, rotá las tres credenciales.

### Probar en Android (funciona el circuito completo, gratis)

```bash
make up                       # backend
cd mobile && npm install
npx expo run:android          # emulador con Google Play, o device
# login -> se registra el token FCM -> reservás, pagás -> push al dueño
#       -> el dueño aprueba -> push al conductor
```

Requiere: JDK 17 (no 21+), Android SDK, emulador con **Google Play** (FCM necesita Play Services). En **Windows** además hace falta un workaround de CMake/rutas largas — ver `mobile/PUSH_NOTIFICATIONS.md`. En macOS/Linux no.

### Probar en iOS

- **Gratis** (solo la parte de la app, en una Mac): `cd mobile && npx expo run:ios` y después
  `./scripts/push-sim.sh ios pending` / `./scripts/push-sim.sh ios confirmed`.
  `xcrun simctl push` inyecta la notificación local → ves que se muestre y que el tap navegue. **No** prueba el registro del token ni el envío del backend (FCM/APNs).
- **Circuito real** (backend → FCM → APNs → device): necesita **Apple Developer Program (US$99/año)** para la APNs Auth Key (subirla a Firebase Console → Cloud Messaging) + **Mac Apple Silicon**. El `.p8` no se commitea.

Detalle completo (config plugins, canal Android, foreground vs background, toolchain): **`mobile/PUSH_NOTIFICATIONS.md`**.

---

## Flujo de trabajo diario (submódulos)

Cada carpeta de un microservicio es un repositorio independiente metido adentro de este repo padre.

### 1. Traer lo último que se subió
Antes de arrancar a programar, para bajarte los últimos cambios que subieron los chicos en todos los microservicios a la vez, parate en la raíz y tirá:

```bash
git submodule update --remote --merge
```

### 2. Modificar código en un servicio
Si tenés que tocar código de un servicio específico (por ejemplo, `auth-service`):
1. Entrás a la carpeta: `cd auth-service`
2. Te parás en la rama en la que estén laburando: `git checkout main`
3. Modificás el código y hacés el push **adentro de esa carpeta**:
   ```bash
   git add .
   git commit -m "fix: Arreglo el error de signup."
   git push
   ```

### 3. Actualizar el puntero en la raíz (clave)
Como actualizaste el microservicio, ese repo avanzó a un nuevo commit. Tenés que avisarle al repo root que use esta nueva versión. Volvés a la raíz y tirás:

```bash
cd ..
git add auth-service
git commit -m "Actualiza puntero de auth-service"
git push
```

Si te olvidás este paso, para cualquiera que clone la raíz de nuevo (o corra `git submodule update`) el submódulo va a seguir apuntando al commit viejo, aunque adentro de esa carpeta vos ya hayas pusheado el cambio.

---

## Variables de entorno / API keys

| Variable | Servicio | Qué hace si no está | Qué poner en producción |
|---|---|---|---|
| `JWT_SECRET` | auth, gateway, payment | Usa `dev-secret-change-me` (¡inseguro!) | Un string largo y aleatorio |
| `BREVO_API_KEY` | auth-service | Loguea el código de verificación en vez de mandar email | API key de [Brevo](https://app.brevo.com/) |
| `TWILIO_*` | auth-service | Loguea el código SMS en vez de mandarlo | Credenciales de [Twilio](https://console.twilio.com) |
| `MERCADOPAGO_ACCESS_TOKEN` | payment-service | El servicio arranca pero crear preferencias de pago falla | Access Token de [MP Developers](https://www.mercadopago.com.ar/developers/panel/app) |
| `MERCADOPAGO_WEBHOOK_SECRET` | payment-service | El webhook no valida firma (modo demo) | Secret del webhook en el panel de MP |
| `MP_FORCE_TEST_PAYER_EMAIL` | payment-service | Usa el email del usuario logueado | Email del comprador de prueba del sandbox de MP |
| `WEBHOOK_BASE_URL` | payment-service | Usa `http://localhost:8004` (MP no puede alcanzarlo) | URL pública del servidor — ver abajo |

### Configurar WEBHOOK_BASE_URL para desarrollo local

Mercado Pago necesita una URL pública para notificarte cuando un pago cambia de estado. En desarrollo local, usá **ngrok** para exponer el payment-service:

```bash
# 1. Instalar ngrok (una sola vez)
brew install ngrok/ngrok/ngrok   # macOS
# o: npm install -g ngrok

# 2. Levantar el túnel (el payment-service corre en el puerto 8004)
npx ngrok http 8004
# → Anotá la URL https://xxxx.ngrok.io que aparece

# 3. Copiá esa URL en tu .env
echo "WEBHOOK_BASE_URL=https://xxxx.ngrok.io" >> .env

# 4. Configurá el mismo endpoint en el panel de MP:
#    MP Developers → tu app → Webhooks → Agregar URL
#    URL: https://xxxx.ngrok.io/api/payments/webhook
#    Eventos: payment

# 5. Reiniciá el payment-service para que tome la nueva variable
docker compose restart payment-service
```

> **Nota:** cada vez que reiniciás ngrok te da una URL distinta. Tenés que actualizar `.env` y el panel de MP.

---

## Booking + Pago: flujo completo

El flujo de reserva tiene varios pasos encadenados. Si alguno falla el siguiente tampoco funciona:

```
[Mobile] spot/[id].tsx
  → Muestra slots disponibles consultando disponibilidad real vía GET /parking-spots/{id}/availability
  → Usuario elige slot y toca "Reservar"

[Mobile] booking/confirm.tsx
  → POST /parking-spots/{spotId}/bookings   (booking-service)
      Crea la reserva en estado PENDING_PAYMENT con hold de 5 min
      Devuelve: { id: "<bookingId>", ... }
  → POST /payments/create-preference        (payment-service)
      Body: { amount, title, externalReference: bookingId }
      Devuelve: { checkoutUrl, preferenceId, externalReference }
  → Abre checkoutUrl en WebBrowser (Expo)
  → Usuario paga en Mercado Pago
  → MP llama al webhook: POST /api/payments/webhook
  → payment-service confirma la reserva: POST /bookings/{bookingId}/confirm
      · cochera instant-booking  → CONFIRMED         → evento booking.confirmed        → push al conductor
      · cochera con aprobación   → PENDING_OWNER_APPROVAL → evento booking.pending_approval → push al propietario
  → MP redirige al deep link parklink://payment/success
  → La app cierra el WebBrowser y navega a la pantalla de reservas

[Mobile] (owner)/bookings/[id].tsx   -- solo si quedó PENDING_OWNER_APPROVAL
  → El propietario toca "Aceptar": POST /bookings/{id}/approve  (booking-service)
      → CONFIRMED → evento booking.confirmed → push al conductor
```

### Errores frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `create-preference` devuelve 500 | `MERCADOPAGO_ACCESS_TOKEN` no configurado o inválido | Revisar token en `.env` y en el panel de MP |
| Webhook no llega | `WEBHOOK_BASE_URL` no es pública | Usar ngrok, ver sección arriba |
| Booking da 409 Conflict | El slot ya está ocupado (otro usuario reservó o hay un hold activo) | El slot no debería haberse mostrado — revisar disponibilidad real |
| Booking da 400 OUTSIDE_PUBLISHED_HOURS | El horario no está en el schedule del parking spot | Verificar que el spot tenga schedule publicado para ese día |
| Booking da 400 INVALID_DATE_RANGE | `start >= end` en el request | Revisar cálculo de fechas en la app |
