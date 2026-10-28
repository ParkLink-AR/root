# Deploy en Render (plan free)

Este repo tiene un [`render.yaml`](./render.yaml) (Blueprint) que define **todo**
lo que hoy corre en `compose.yaml`: 6 Web Services (`gateway`, `auth-service`,
`parking-service`, `booking-service`, `payment-service`, `notifications-service`),
1 Postgres free (compartida entre los 5 servicios que necesitan base -- Render
free sólo permite una base activa por cuenta, ver sección 6) y el
`admin-dashboard` como Static Site.

Todo queda armado solo al importar el Blueprint -- bases de datos, PostGIS,
y todos los secretos compartidos entre servicios (JWT, claves internas,
Brevo, Cloudflare R2, Mercado Pago). Dos cosas no se pueden autoprovisionar:
RabbitMQ (paso 3, no es una cuenta que se cree por API) y Twilio (paso 4,
credenciales de una cuenta de mensajería que preferimos no commitear).

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

## 4. Twilio (código de verificación de teléfono por SMS)

`auth-service` manda el código de 6 dígitos del registro (y del cambio de
teléfono) por SMS vía Twilio (ver `auth-service/app/utils/sms.py`). Ya está
armada y probada (cuenta paga + compliance profile aprobado), pero las
credenciales van a mano en el dashboard de Render, no en este archivo:

1. Dashboard de Render → `parklink-auth-service` → pestaña **Environment**:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_FROM_NUMBER` (el número comprado, formato `+1...`)
2. Cambiá `SKIP_PHONE_VERIFICATION` a `"false"` en el mismo servicio (el
   Blueprint la trae en `"true"` para no bloquear el registro hasta que
   pegues las tres de arriba) y sincronizá.
3. En `mobile/.env` (o la rama que uses para apuntar a este deploy), poné
   `EXPO_PUBLIC_SKIP_PHONE_VERIFICATION=false` y reconstruí la app -- si no,
   el wizard de registro sigue saltando el paso de código aunque el backend
   ya lo esté exigiendo.

Si en algún momento hay que armar la cuenta de cero: cuenta paga en
https://console.twilio.com (la trial no sirve, solo deja usar plantillas
enlatadas sin lugar para nuestro código real) + comprar un número con
capacidad SMS (Phone Numbers → Buy a number, ~1.15 USD/mes) + **Trust Hub →
Profiles → Primary compliance profile** completado como **Individual** (solo
datos personales, sin documentación de negocio) y aprobado -- aprobación en
hasta 48hs, sin esto Twilio devuelve `20003 Primary compliance profile is not
approved` y no deja mandar ningún SMS.

Ojo con el saldo: Twilio cobra ~0.10 USD por SMS a números argentinos,
descontado de un saldo prepago que cargás con tarjeta -- si se agota, deja de
mandar (no te cobra de más solo). Sin las tres variables de arriba,
`auth-service` cae en modo log-only (loguea el código en vez de mandarlo).

## 5. Mercado Pago: credenciales reales

`MERCADOPAGO_ACCESS_TOKEN` / `MERCADOPAGO_WEBHOOK_SECRET` van como
`sync: false`: cargalas en el dashboard de `parklink-payment-service` con los
mismos valores de `payment-service/.env` (o credenciales nuevas de
https://www.mercadopago.com.ar/developers).

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
`parklink-gateway` (`https://parklink-gateway.onrender.com`). Si ya
completaste la sección 4 (Twilio configurado y `SKIP_PHONE_VERIFICATION` en
`"false"`), poné también `EXPO_PUBLIC_SKIP_PHONE_VERIFICATION=false` para que
el wizard de registro pida el código real.

## 8. Secretos

`render.yaml` no trae ningún secreto: los de Brevo, Cloudflare R2, Mercado
Pago y Twilio van como `sync: false` y se cargan a mano en el dashboard de
cada servicio, con los mismos valores de tu `.env` local.
