# Deploy en un VPS de Hetzner

Alternativa a `DEPLOY.md` (Render): en vez de un servicio administrado por cada
Web Service, esto corre el `compose.yaml` de este repo **tal cual** en un solo
servidor propio. Cada microservicio conserva su propia base Postgres (nunca
hubo que compartir una sola como en el plan free de Render), y RabbitMQ corre
como un contenedor más del mismo compose -- sin necesidad de CloudAMQP.

Costo estimado: un CX22 (2 vCPU, 4 GB RAM, 40 GB SSD) ronda 4,50 USD/mes,
facturado por hora/mes real sin letra chica de renovación. Contra los ~49
USD/mes de Render en su plan pago (6 Web Services + 1 Postgres, todos
Starter), o el sleep/expiración del plan free. Es el punto de partida más
barato -- sin mucho margen para 5 Postgres + RabbitMQ + 6 servicios a la vez,
pero Hetzner deja resizear el mismo server sin recrearlo si hace falta más
adelante.

## 1. Crear el servidor

1. Cuenta en https://www.hetzner.com/cloud, agregar un método de pago.
2. **New Server** → ubicación (Falkenstein/Nuremberg o Ashburn/Hillsboro si
   la mayoría de los usuarios está en América), imagen **Ubuntu 24.04**, tipo
   **CX22** (2 vCPU / 4 GB RAM / 40 GB SSD -- el punto de partida más barato
   para 5 Postgres + RabbitMQ + 6 servicios chicos, justo pero funciona; si
   con el tiempo se siente lento, Hetzner deja resizear el mismo server sin
   recrearlo).
3. Agregar tu clave pública SSH en el wizard de creación (no uses password
   auth).
4. Activar el **Hetzner Cloud Firewall** del server: permitir entrante solo
   `22` (SSH, idealmente restringido a tu IP), `80` y `443` (HTTP/HTTPS). Todo
   lo demás (Postgres, RabbitMQ, los puertos internos de cada servicio)
   nunca necesita estar expuesto a internet -- solo se hablan entre sí dentro
   de la red interna de Docker Compose.

## 2. Preparar el servidor

Conectate por SSH (`ssh root@<ip-del-server>`) e instalá Docker:

```bash
curl -fsSL https://get.docker.com | sh
# El script de Docker ya deja el daemon habilitado en el boot (systemd) --
# los contenedores con restart: unless-stopped vuelven solos después de un
# reinicio del servidor, sin necesidad de un unit de systemd aparte.
apt-get install -y docker-compose-plugin
```

## 3. Clonar el repo (submódulos privados)

Los submódulos (`auth-service`, `booking-service`, `gateway`, `parking-service`,
`payment-service`, `notifications-service`) son repos privados de
`ParkLink-AR`. Generá una clave SSH nueva en el servidor y agregala como
**Deploy Key** (con acceso de lectura) en cada uno de esos repos de GitHub, o
más simple: agregala una sola vez como clave del usuario/máquina que tiene
acceso a todo el org.

```bash
ssh-keygen -t ed25519 -C "hetzner-parklink" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub   # pegar en GitHub → Settings → SSH and GPG keys
                            # (o como Deploy Key por repo si preferís acceso acotado)

git clone --recurse-submodules git@github.com:ParkLink-AR/root.git parklink
cd parklink
```

## 4. Variables de entorno de producción

Cada microservicio tiene sus secretos en su propio `<servicio>/.env` (fuera de
git): JWT, Cloudflare R2, Brevo, Mercado Pago, Twilio. Copialos desde tu máquina:

```bash
# Desde tu máquina, no desde el servidor:
cd /home/numeral/Escritorio/ParkLink/root
for s in auth-service booking-service gateway notifications-service parking-service payment-service; do
  scp $s/.env root@<ip-del-server>:~/parklink/$s/.env
done
scp -r /home/numeral/Escritorio/ParkLink/root/notifications-service/secrets root@<ip-del-server>:~/parklink/notifications-service/secrets
```

Ajustá en esos `.env`, ya en el servidor, lo que cambia entre local y
producción:

- `ENVIRONMENT=production` (en cada servicio que lo tiene)
- `CORS_ORIGINS=https://admin.tu-dominio.com,https://tu-dominio.com` en
  `gateway/.env` y `payment-service/.env` (nunca `*` en producción).
- `JWT_SECRET` (auth, gateway, payment), `GATEWAY_INTERNAL_SECRET` (todos) e
  `INTERNAL_SERVICE_KEY` (todos menos gateway): conviene generar valores
  propios de producción (`openssl rand -hex 32`), el mismo valor en cada
  servicio que lo usa.

## 5. Restart policy (falta en el compose actual)

Hoy `compose.yaml` no declara `restart:` en ningún servicio -- en local no
importa (lo levantás vos a mano), pero en un servidor real un contenedor que
se cae (o un reinicio del servidor por una actualización de Ubuntu) lo deja
caído hasta que alguien entre a mano y corra `docker compose up -d` de nuevo.
Antes de ir a producción, agregar `restart: unless-stopped` a cada servicio
del compose (las 5 bases, rabbitmq, y los 6 microservicios) es el único
cambio de código pendiente para este deploy -- no lo hice todavía porque
todavía estamos en la etapa de planear, no de tocar el compose.

## 6. TLS y reverse proxy (Caddy)

Solo el `gateway` publica un puerto (`8080:8080` en `compose.yaml`) -- es lo
único que necesita quedar detrás de HTTPS público; las 5 bases y RabbitMQ
siguen sin exponerse. Caddy resuelve el certificado (Let's Encrypt) solo,
sin configuración manual:

```
# /etc/caddy/Caddyfile (o como servicio Docker más -- lo que prefieras)
api.tu-dominio.com {
    reverse_proxy localhost:8080
}
```

Apuntá el DNS de `api.tu-dominio.com` (registro A) a la IP del server antes
de arrancar Caddy, si no Let's Encrypt no puede validar el dominio.

## 7. Levantar todo

```bash
cd ~/parklink
docker compose up -d --build
docker compose ps   # confirmar que las 5 bases + rabbitmq queden healthy
                     # antes de que los servicios que dependen de ellas arranquen bien
```

## 8. Apuntar mobile y admin-web al nuevo backend

- `mobile/.env`: `EXPO_PUBLIC_API_URL=https://api.tu-dominio.com`
- Cloudflare Pages del admin-web: variable de entorno
  `EXPO_PUBLIC_API_URL` con la misma URL, en la configuración del proyecto
  (no en el repo).

## 9. Backups de las bases

Sin un plan gestionado, los backups quedan a mano. Algo simple con `pg_dump`
+ cron alcanza para empezar:

```bash
# /root/backup-dbs.sh
#!/bin/bash
STAMP=$(date +%F)
for db in auth parking booking payment notifications; do
  docker compose -f ~/parklink/compose.yaml exec -T db-$db \
    pg_dump -U postgres "${db}_db" | gzip > /root/backups/${db}-${STAMP}.sql.gz
done
```

Correrlo por cron una vez al día, y copiar `/root/backups` fuera del server
de tanto en tanto (a Cloudflare R2, que ya tenés configurado, o a tu propia
máquina) -- un backup que vive solo en el mismo disco que puede fallar no
protege de mucho.

## 10. Deploys siguientes

```bash
cd ~/parklink
git pull
git submodule update --remote --merge   # o --checkout si preferís pointers exactos
docker compose up -d --build
```
