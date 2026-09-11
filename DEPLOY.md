# Deploy en Render (plan free)

Este repo tiene un [`render.yaml`](./render.yaml) (Blueprint) que define **todo**
lo que hoy corre en `compose.yaml`: 6 Web Services (`gateway`, `auth-service`,
`parking-service`, `booking-service`, `payment-service`, `notifications-service`),
5 Postgres free (uno por servicio) y el `admin-dashboard` como Static Site.

Todo queda armado solo al importar el Blueprint -- bases de datos, PostGIS,
y todos los secretos compartidos entre servicios (JWT, claves internas,
Brevo, Cloudflare R2, Mercado Pago). Lo único que no se puede autoprovisionar
es RabbitMQ (Render no tiene un plan gestionado) -- ver el paso 3.

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

Cada servicio se conecta solo a su propia base (`fromDatabase` en el YAML),
PostGIS se habilita solo la primera vez que arranca `parking-service` (ver
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

## 4. Mercado Pago: credenciales reales

Las credenciales que trae el Blueprint (`MERCADOPAGO_ACCESS_TOKEN` /
`MERCADOPAGO_WEBHOOK_SECRET`) son las mismas que ya usás en local (`root/.env`)
-- lo que sea que hagan ahí (test o real) va a hacer acá. Si querés otro modo
o cuenta, generá credenciales nuevas en
https://www.mercadopago.com.ar/developers y reemplazalas en el YAML o
directo en el dashboard de `parklink-payment-service`.

## 5. Advertencia sobre el plan free

Cosas a tener en cuenta (verificá los números actuales en tu dashboard de
Render, cambian con el tiempo):

- **Sleep**: los Web Services free se duermen tras ~15 min sin tráfico y
  tardan unos segundos en despertar en el próximo request.
- **Postgres free expira**: cada instancia free tiene un límite de días
  antes de requerir upgrade a un plan pago -- revisá la fecha en el
  dashboard apenas se creen (son 5 instancias distintas, cada una con su
  propia fecha).
- Sin disco persistente no es un problema: avatares y fotos de cochera se
  suben a Cloudflare R2, no a disco local, así que sobreviven redeploys.

## 6. Probar la app mobile contra este deploy

En `mobile/.env`, cambiá `EXPO_PUBLIC_API_URL` a la URL de
`parklink-gateway` (`https://parklink-gateway.onrender.com`).

## 7. Seguridad de lo que va commiteado en `render.yaml`

Este es un proyecto personal privado, así que `render.yaml` trae embebidas
las credenciales reales de Brevo, Cloudflare R2 y Mercado Pago (mismo
criterio que ya se usa para el JSON de Firebase de `notifications-service`,
ver `mobile/PUSH_NOTIFICATIONS.md`) -- así el Blueprint queda completo sin
pasos manuales. **Si este repo alguna vez se hace público, rotá las tres
credenciales primero** (Brevo → Settings → API Keys; Cloudflare → R2 →
Manage API Tokens; Mercado Pago → Developers → Credenciales) y actualizá
`render.yaml` con los valores nuevos antes de sacarlo a la luz.
