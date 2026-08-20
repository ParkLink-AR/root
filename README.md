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
