# Deploy en Render (plan free)

Este repo tiene un [`render.yaml`](./render.yaml) (Blueprint) que define todo
lo que hoy corre en `compose.yaml`, adaptado a Render: 4 Web Services
(`gateway`, `auth-service`, `parking-service`, `payment-service`), 1 Postgres
free y el `admin-dashboard` como Static Site.

Lo que **no** se puede resolver solo con el YAML queda acá.

## Qué no entra en el deploy (y por qué)

- **rabbitmq**: nada lo consume todavía (`notifications-service` no tiene
  código) y `gateway/app/rabbitmq.py` ya tolera que no esté disponible
  (loguea `[RABBITMQ] Could not connect... continuing without it`, no tira
  abajo el servicio). Se agrega el día que `notifications-service` exista.
- **booking-service / notifications-service**: sin código, igual que en el
  compose local.
- **mobile**: es una app Expo, Render no la hostea. Para probarla contra
  este deploy, en `mobile/.env` poné `EXPO_PUBLIC_API_URL=https://parklink-gateway.onrender.com`.

## 1. Dar acceso a Render a los submódulos

Este repo raíz usa Git submodules (`auth-service`, `parking-service`,
`payment-service`, `gateway`, todos privados en `ParkLink-AR`). Cuando
conectes el repo en Render, instalá el GitHub App de Render con acceso a
**todos** esos repos del org (no solo a `root`) — si no, el build falla al
clonar los submódulos con un error de permisos.

## 2. Importar el Blueprint

Dashboard de Render → **New** → **Blueprint** → elegí este repo → Render lee
`render.yaml` y te muestra el plan (4 servicios + 1 DB + 1 static site).
Confirmá. Si algún campo del YAML quedó desactualizado (Render cambia el
schema de tanto en tanto), el import te va a marcar la línea exacta con el
error — anda a https://render.com/docs/blueprint-spec y renombrá esa key.

## 3. Postgres: una sola instancia free, tres bases

Render permite **una** instancia Postgres free por cuenta. El compose local
usa tres (`db-auth`, `db-parking` con PostGIS, `db-payment`); acá comparten
una sola instancia (`parklink-postgres`, con la base `parklink_auth_db` ya
creada por el Blueprint).

Después de que la instancia esté arriba:

1. Abrí el **psql** desde el dashboard de Render (o copiá el "External
   Connection String" y conectate con tu cliente favorito).
2. Creá las dos bases que faltan y habilitá PostGIS en la de parking:
   ```sql
   CREATE DATABASE parking_service;
   CREATE DATABASE payment_db;
   \c parking_service
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```
3. Armá las `DATABASE_URL`/credenciales para `parking-service` y
   `payment-service` a partir de la misma connection string de
   `parklink-postgres` (mismo host/puerto/usuario/contraseña, cambiando el
   nombre de la base al final):
   - `parking-service` no usa una sola `DATABASE_URL` sino
     `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` sueltos (ya viene
     `DB_NAME=parking_service` en el YAML) — completá los otros 4 con los
     valores de la instancia compartida.
   - `payment-service` sí usa `DATABASE_URL` completa, con `payment_db` al
     final.
   Estos quedaron como `sync: false` en el `render.yaml` (Render no puede
   armarlos solo porque no sabe de antemano el nombre de la base "hija") —
   completalos a mano en cada servicio, pestaña **Environment**.

## 4bis. Cloudflare R2 (avatares y fotos de cochera)

`auth-service` y `parking-service` suben ahí las imágenes en vez de a disco
local. Es un solo bucket, usado por ambos servicios (`parking-service` toma
las credenciales de `parklink-auth-service` vía `fromService` en el
`render.yaml`, así que solo hace falta cargarlas una vez):

1. Creá una cuenta en https://dash.cloudflare.com si no tenés (el free tier
   de R2 alcanza de sobra: 10GB de storage, sin costo de egress).
2. **R2** (menú lateral) → **Create bucket** → nombre a elección (ej.
   `parklink`).
3. Entrá al bucket → **Settings** → **Public access** → habilitá el
   "R2.dev subdomain". Te da una URL tipo `https://pub-xxxxxxxx.r2.dev` —
   esa es `R2_PUBLIC_URL`.
4. **R2** → **Manage API Tokens** → **Create API Token** → permisos
   "Object Read & Write" scopeado a ese bucket. Te da un Access Key ID y
   Secret Access Key (`R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY`).
5. El Account ID (`R2_ACCOUNT_ID`) está en la URL del dashboard o en la
   barra lateral de la cuenta.
6. En el dashboard de Render, pestaña **Environment** de
   `parklink-auth-service`, completá las 5 `R2_*` (`R2_BUCKET_NAME` es el
   nombre que le pusiste en el paso 2). `parklink-parking-service` las toma
   solo de ahí, no hace falta repetirlas.

## 4. Secrets a completar a mano

Estos quedaron vacíos (`sync: false`) en el Blueprint porque son
credenciales reales, no algo para versionar en `render.yaml`:

**No van commiteadas a `render.yaml`** — son credenciales reales, y ese
archivo queda en el historial de git para siempre. Se pegan a mano en el
dashboard de Render, pestaña **Environment** de cada servicio, después del
primer deploy.

Checklist mínima para que los 4 servicios levanten (nada de esto habilita
pagos reales de Mercado Pago — para eso hace falta sacar credenciales TEST
propias desde Mercado Pago Developers y volver a esta sección):

| Servicio | Variable | Qué poner |
| --- | --- | --- |
| auth-service | `BREVO_API_KEY` | El valor real que ya tenés en tu `.env` local (la línea `BREVO_API_KEY=xkeysib-...`) — copialo tal cual. |
| auth-service | `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | Dejalos vacíos. Sin Twilio, cae a loguear el código de SMS — no rompe nada porque `SKIP_EMAIL_VERIFICATION=true`. |
| parking-service | `DB_HOST` / `DB_USER` / `DB_PASSWORD` | Los de tu instancia `parklink-postgres` compartida (ver sección 3). |
| payment-service | `DATABASE_URL` | La misma connection string de `parklink-postgres`, con `payment_db` al final (ver sección 3). |
| payment-service | `MERCADOPAGO_ACCESS_TOKEN` | Literal `APP_USR-REEMPLAZAR` (mismo placeholder que tu `.env.example`) — el servicio necesita que la variable no esté vacía para arrancar, aunque el valor no sea válido. Crear una preferencia de pago real va a fallar hasta que pongas una de verdad. |
| payment-service | `MERCADOPAGO_WEBHOOK_SECRET` | Literal `REEMPLAZAR_CON_LA_SECRET_DE_MERCADO_PAGO`, mismo motivo. |
| payment-service | `MP_FORCE_TEST_PAYER_EMAIL` | Dejalo vacío. |
| payment-service | `FRONTEND_SUCCESS_URL` / `FRONTEND_FAILURE_URL` / `FRONTEND_PENDING_URL` | No hay un frontend de pagos real deployado todavía — poné algo tipo `https://parklink-mobile-web.onrender.com/payment/success` (ajustalo cuando ese servicio exista) o dejalas en `http://localhost:19006/payment/...` si solo vas a probar con Postman/admin-dashboard. |

`auth-service` cae a modo dev sin `BREVO_API_KEY` (logueando el código de
verificación) pero como sí tenés una key real, los emails de verdad van a
salir — revisá que el remitente (`no-reply@mail.parklink.com.ar`) esté
verificado en tu cuenta de Brevo o Brevo va a rechazar el envío.

## 5. Advertencia sobre el plan free

Cosas a tener en cuenta (verificá los números actuales en tu dashboard de
Render, cambian con el tiempo):

- **Sleep**: los Web Services free se duermen tras ~15 min sin tráfico y
  tardan unos segundos en despertar en el próximo request — vas a notar esa
  latencia la primera vez que uses el dashboard después de un rato.
- ~~Sin disco persistente~~: ya no aplica -- avatares y fotos de cochera se
  suben a Cloudflare R2 en vez de disco local (ver sección 4bis), así que
  sobreviven redeploys sin depender de un volumen.
- **Postgres free expira**: las instancias free de Render tienen un límite
  de días antes de requerir upgrade a un plan pago — revisá la fecha en el
  dashboard apenas la crees.

## 6. ~~Bug pre-existente que vas a notar en el admin-dashboard~~ (arreglado)

`admin-dashboard/api.js` le pega **directo** a `payment-service`
(`CONFIG.PAYMENT_URL`), no a través del gateway. `payment-service` ahora
manda `Access-Control-Allow-Origin` (paquete `cors`, ver
`payment-service/src/app.js`), configurable con la env var `CORS_ORIGINS`
(`PAYMENT_CORS_ORIGINS` en el `.env`/`render.yaml` de la raíz) — por defecto
`*`, restringila a `https://parklink-admin-dashboard.onrender.com` en
producción si querés cerrarlo más.
