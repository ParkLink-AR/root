# Deploy en Render (plan free)

Este repo tiene un [`render.yaml`](./render.yaml) (Blueprint) que define **todo**
lo que hoy corre en `compose.yaml`: 6 Web Services (`gateway`, `auth-service`,
`parking-service`, `booking-service`, `payment-service`, `notifications-service`),
1 Postgres free (compartida entre los 5 servicios que necesitan base -- Render
free sólo permite una base activa por cuenta, ver sección 6) y el
`admin-dashboard` como Static Site.

Todo queda armado solo al importar el Blueprint -- bases de datos, PostGIS,
y todos los secretos compartidos entre servicios (JWT, claves internas,
Brevo, Cloudflare R2, Mercado Pago). Dos cosas no se pueden autoprovisionar
porque son cuentas de terceros que tenés que crear vos: RabbitMQ (paso 3) y
WhatsApp Cloud API para el código de verificación de teléfono (paso 4).

## 1. Dar acceso a Render a los submódulos

Este repo raíz usa Git submodules (`auth-service`, `parking-service`,
`booking-service`, `payment-service`, `notifications-service`, `gateway`,
todos privados en `ParkLink-AR`). Cuando conectes el repo en Render, instalá
el GitHub App de Render con acceso a **todos** esos repos del org (no solo a
`root`) -- si no, el build falla al clonar los submódulos con un error de
permisos.

## 2. Importar el Blueprint

Dashboard de Render → **New** → **Blueprint** → elegí este repo → Render lee
`render.yaml` y te muestra el plan (6 servicios + 5 DBs + 1 static site).
Confirmá. Si algún campo del YAML quedó desactualizado (Render cambia el
schema de tanto en tanto), el import te va a marcar la línea exacta con el
error -- andá a https://render.com/docs/blueprint-spec y renombrá esa key.

Los 5 servicios comparten la misma base Postgres (`fromDatabase` en el
YAML) -- Render free sólo permite una base activa por cuenta, así que no
hay 5 instancias separadas. No hay colisión de tablas entre servicios
(nombres únicos: `users`/`refresh_tokens`/... de auth, `parking_spots`/...
de parking, `transactions` de payment, `bookings`/... de booking,
`device_tokens`/... de notifications). PostGIS se habilita solo la
primera vez que arranca `parking-service` (ver
`parking-service/src/config/typeorm.config.ts`), y los secretos compartidos
(`JWT_SECRET`, `GATEWAY_INTERNAL_SECRET`, `INTERNAL_SERVICE_KEY`) se generan
una vez y se reusan entre servicios. No hay que tocar nada de eso a mano.

## 3. RabbitMQ (el único paso manual)

`booking-service` necesita RabbitMQ para arrancar (publica ahí los eventos
`booking.confirmed`/`booking.pending_approval` que `notifications-service`
consume para mandar las push). Render no tiene un plan gestionado gratis:

1. Creá una cuenta free en https://www.cloudamqp.com (plan "Little Lemur",
   sin costo) -- te da una URL `amqps://usuario:pass@host/vhost`.
2. Dashboard de Render → `parklink-booking-service` → pestaña
   **Environment** → pegá esa URL en `RABBITMQ_URL`.
3. `gateway` y `notifications-service` la toman de ahí solas
   (`fromService` en el YAML) -- no hace falta repetirla.

Sin este paso, `booking-service` no arranca (se cae con `rabbitmq dial`)
-- es el primer servicio a revisar si el deploy falla.

## 4. WhatsApp Cloud API (código de verificación de teléfono)

`auth-service` manda el código de 6 dígitos del registro (y del cambio de
teléfono) por WhatsApp, vía la Cloud API de Meta (ver
`auth-service/app/utils/whatsapp.py`) -- es la API oficial de Meta, directo,
sin intermediarios de terceros.

1. Creá una app en https://developers.facebook.com/apps (tipo "Business") y
   agregale el producto **WhatsApp**.
2. **WhatsApp → API Setup** te da un **Phone Number ID** y un token temporal
   (dura 24h, sirve para probar). Para producción, generá uno permanente:
   **Business Settings → Users → System Users** → creá uno, asignale el
   activo de WhatsApp, y generá un token sin fecha de expiración.
3. **WhatsApp Manager → Account tools → Message templates** → creá una
   plantilla con categoría **Authentication** (Meta escribe el texto del
   mensaje solo -- "\<código\> es tu código de verificación" -- vos sólo
   elegís nombre, idioma y opciones como el pie con el tiempo de expiración).
   La aprobación suele tardar minutos, no días.
4. Dashboard de Render → `parklink-auth-service` → pestaña **Environment**:
   - `WHATSAPP_ACCESS_TOKEN`: el token del paso 2.
   - `WHATSAPP_PHONE_NUMBER_ID`: el ID del paso 2.
   - Si tu plantilla no se llama `otp_code` o no está en `es_AR`, actualizá
     también `WHATSAPP_TEMPLATE_NAME`/`WHATSAPP_TEMPLATE_LANG` (ya vienen
     seteados en el Blueprint, pero apuntando a esos valores por default).
5. Cambiá `SKIP_PHONE_VERIFICATION` a `"false"` en el mismo servicio (el
   Blueprint la trae en `"true"` para no bloquear el registro hasta que
   completes los pasos de arriba) y sincronizá.
6. En `mobile/.env` (o la rama que uses para apuntar a este deploy), poné
   `EXPO_PUBLIC_SKIP_PHONE_VERIFICATION=false` y reconstruí la app -- si no,
   el wizard de registro sigue saltando el paso de código aunque el
   backend ya lo esté exigiendo, y el usuario nunca ve la pantalla para
   escribirlo.

Sin los pasos 4-5, el registro no se rompe: `auth-service` cae en modo
log-only (loguea el código en vez de mandarlo), igual que en local sin estas
variables -- pero ningún usuario real puede completar el paso de teléfono,
porque el código nunca le llega.

## 5. Mercado Pago: credenciales reales

Las credenciales que trae el Blueprint (`MERCADOPAGO_ACCESS_TOKEN` /
`MERCADOPAGO_WEBHOOK_SECRET`) son las mismas que ya usás en local (`root/.env`)
-- lo que sea que hagan ahí (test o real) va a hacer acá. Si querés otro modo
o cuenta, generá credenciales nuevas en
https://www.mercadopago.com.ar/developers y reemplazalas en el YAML o
directo en el dashboard de `parklink-payment-service`.

## 6. Advertencia sobre el plan free

Cosas a tener en cuenta (verificá los números actuales en tu dashboard de
Render, cambian con el tiempo):

- **Sleep**: los Web Services free se duermen tras ~15 min sin tráfico y
  tardan unos segundos en despertar en el próximo request.
- **Postgres free expira**: la instancia free tiene un límite de días
  antes de requerir upgrade a un plan pago -- revisá la fecha en el
  dashboard apenas se cree.
- Sin disco persistente no es un problema: avatares y fotos de cochera se
  suben a Cloudflare R2, no a disco local, así que sobreviven redeploys.

## 7. Probar la app mobile contra este deploy

En `mobile/.env`, cambiá `EXPO_PUBLIC_API_URL` a la URL de
`parklink-gateway` (`https://parklink-gateway.onrender.com`).

## 8. Seguridad de lo que va commiteado en `render.yaml`

Este es un proyecto personal privado, así que `render.yaml` trae embebidas
las credenciales reales de Brevo, Cloudflare R2 y Mercado Pago (mismo
criterio que ya se usa para el JSON de Firebase de `notifications-service`,
ver `mobile/PUSH_NOTIFICATIONS.md`) -- así el Blueprint queda completo sin
pasos manuales. **Si este repo alguna vez se hace público, rotá esas
credenciales primero** (Brevo → Settings → API Keys; Cloudflare → R2 →
Manage API Tokens; Mercado Pago → Developers → Credenciales) y actualizá
`render.yaml` con los valores nuevos antes de sacarlo a la luz.

`WHATSAPP_ACCESS_TOKEN`/`WHATSAPP_PHONE_NUMBER_ID` quedan afuera de esa
lista a propósito -- van como `sync: false` (paso manual, sección 4) en vez
de embebidos, porque no los tengo para poner acá. Si en algún momento los
pegás directo en el YAML en vez de en el dashboard, aplicá el mismo criterio:
rotalos antes de hacer público el repo.
