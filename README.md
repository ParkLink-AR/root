# ParkLink AR - root

Este es el repositorio raíz de ParkLink. Contiene la configuración global para levantar el entorno local (Docker Compose + Makefile) y agrupa todos los microservicios del sistema usando Git Submodules.

---

## Servicios

| Servicio | Puerto | Submódulo | ¿Está en `docker compose up`? |
|---|---|---|---|
| `gateway` | 8080 | [gateway](https://github.com/ParkLink-AR/gateway) | Sí |
| `auth-service` | 8000 | [auth-service](https://github.com/ParkLink-AR/auth-service) | Sí |
| `parking-service` | 3001 | [parking-service](https://github.com/ParkLink-AR/parking-service) | Sí |
| `payment-service` | 8004 | [payment-service](https://github.com/ParkLink-AR/payment-service) | Sí |
| `mobile` (app Expo) | 8081 por defecto (lo elige Expo) | [mobile](https://github.com/ParkLink-AR/mobile) | No, se corre aparte (ver [Conectar la app mobile](#conectar-la-app-mobile)) |
| `booking-service` | — | [booking-service](https://github.com/ParkLink-AR/booking-service) | No todavía — ya tiene código (Go) y su propio `docker-compose.yml`/`Makefile`, pero no está enchufado al compose de la raíz |
| `notifications-service` | — | [notifications-service](https://github.com/ParkLink-AR/notifications-service) | No todavía — sólo consume eventos de RabbitMQ, aún sin código |

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
cp .env.example .env
```

Con el `.env` tal cual viene (todo vacío/con defaults de desarrollo) el sistema **ya funciona**: los servicios que necesitan una API key externa (email, SMS, Mercado Pago) caen a un modo "dev" que loguea lo que haría en vez de fallar. Ver [Variables de entorno / API keys](#variables-de-entorno--api-keys) para el detalle de cada una y cuándo hace falta completarla de verdad.

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

### 3. Verificar que levantó todo

```bash
docker compose ps
curl http://localhost:8080/health   # el gateway responde qué servicios tiene configurados y si RabbitMQ conectó
```

`auth-service` (y el propio `gateway`) además exponen su `/livez`/`/readyz` directo, sin pasar por el proxy: `curl http://localhost:8000/livez`.

---

## Variables de entorno / API keys

Todas viven en el `.env` de la raíz (un solo archivo para todo el stack de Docker Compose). Cada servicio también tiene su propio `.env.example` más detallado por si lo corrés suelto, fuera de este compose.

### `JWT_SECRET` — el más importante

Lo usan **tanto `auth-service` como `gateway`**, y **tienen que coincidir**: `auth-service` firma el access token al hacer login, `gateway` lo verifica en cada request a una ruta protegida (`REQUIRED`) antes de reenviarla. Si en algún momento corrés estos dos servicios por separado (no vía este `docker compose`) y no coinciden, todo el tráfico autenticado va a devolver 401 aunque el login haya funcionado bien. El default de desarrollo (`dev-secret-change-me`) es el mismo en ambos automáticamente porque comparten el mismo `.env` acá.

### Email — Brevo (`BREVO_API_KEY`)

Usado por `auth-service` para mandar los códigos de verificación de email (registro, cambio de email, reset de contraseña). Sin la key:

```
[MAIL][DEV] Código de verificación para alguien@mail.com: 123456
```

queda logueado en `docker compose logs -f auth-service` en vez de mandarse un mail real — perfecto para probar el flujo completo en local sin cuenta de Brevo. Conseguí una key real en [app.brevo.com](https://app.brevo.com) (plan gratis alcanza) si necesitás que el mail llegue de verdad.

### SMS — Twilio (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`)

Mismo criterio que el email, para el código de verificación de teléfono: sin credenciales, `[SMS][DEV] Código de verificación para +549...: 123456` queda en el log de `auth-service`. Las credenciales reales salen de [console.twilio.com](https://console.twilio.com) — ojo que `TWILIO_ACCOUNT_SID` es el *Account SID* (empieza con `AC`), no un API Key SID (`SK`). Las cuentas trial de Twilio además sólo mandan SMS de texto libre a números verificados manualmente en la consola; para SMS real a cualquier número hace falta upgradear la cuenta.

### `SKIP_EMAIL_VERIFICATION`

- `false` (default en `.env.example`): el flujo real — hay que verificar email y teléfono con código antes de poder loguearse. Es lo que prueba mobile.
- `true`: saltea esa verificación al registrarse. Sirve para tests automatizados o para no tener que copiar códigos de los logs constantemente, pero no representa el flujo real de la app.

### Mercado Pago (`MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`)

Usadas por `payment-service`. Sin credenciales reales el servicio arranca igual (necesita que las variables no estén vacías, por eso el placeholder `APP_USR-REEMPLAZAR`), pero crear una preferencia de pago de verdad va a fallar. Sacá credenciales de **prueba** (TEST, no producción) desde [Mercado Pago Developers](https://www.mercadopago.com.ar/developers/panel).

### Nominatim (`NOMINATIM_BASE_URL`, `NOMINATIM_USER_AGENT`)

Usado por `parking-service` para geocodificar direcciones. Por default pega contra el servidor público de OpenStreetMap, que tiene rate-limit y pide un `User-Agent` identificable (ya viene seteado) — para uso intensivo conviene un servidor Nominatim propio.

### Lo que **no** hace falta tocar

- `DATABASE_URL` de cada servicio: apuntan a las bases `db-*` de este mismo compose, no son configurables desde el `.env` de la raíz a propósito.
- Las fotos de perfil (`avatar_url`) se guardan en el volumen `parklink_auth_avatars`, servidas por `auth-service` vía `/static` y proxeadas por el gateway — no necesitan configuración extra, pero si corrés `make clean` se pierden junto con la base.

---

## Conectar la app mobile

`mobile` es una app Expo, no está en el `docker compose` de la raíz — se corre aparte:

```bash
cd mobile
cp .env.example .env   # ya trae EXPO_PUBLIC_API_URL=http://localhost:8080, andá al archivo si necesitás cambiarlo
npm install
npx expo start
```

`EXPO_PUBLIC_API_URL` es la única variable que necesita, y tiene que apuntar al **gateway** (no a un microservicio directo). El valor por default (`http://localhost:8080`) funciona tal cual para web y simulador iOS corriendo en la misma máquina que `docker compose`. Para emulador Android usá `http://10.0.2.2:8080`; para un dispositivo físico, la IP LAN de la máquina que corre Docker (ej. `http://192.168.1.50:8080`), con el celular en la misma red — el detalle completo está en `mobile/.env.example`.

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
