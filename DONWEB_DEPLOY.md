# Deploy en un Cloud Server de DonWeb

Alternativa a `DEPLOY.md` (Render) y `HETZNER_DEPLOY.md`: igual que con Hetzner,
esto corre el `compose.yaml` de este repo **tal cual** en un solo servidor
propio, con cada microservicio conservando su propia base Postgres y
RabbitMQ corriendo como un contenedor más del mismo compose -- sin
CloudAMQP. La diferencia con Hetzner es solo quién provee el VPS: a partir
del paso 2 (instalar Docker) todo este documento es igual para cualquier VPS
Ubuntu, sea DonWeb, Hetzner o cualquier otro.

Ventaja de DonWeb sobre Hetzner para este proyecto: factura en pesos
argentinos (sin el recargo de tarjeta en dólares) y el datacenter está en
Argentina, así que la latencia hacia usuarios locales es menor. La contra ya
charlada: por specs equivalentes suele salir más caro que Hetzner -- el
armador de DonWeb (donweb.com/es-ar/cloud-server-vps) es un configurador con
sliders, no tiene planes fijos publicados, así que el precio exacto para 4
vCPU / 4 GB RAM / 40 GB hay que verlo ahí mismo antes de confirmar.

## 1. Crear el servidor

1. Cuenta en https://donweb.com/es-ar/cloud-server-vps, agregar un método de
   pago.
2. **Armar a medida**: elegí **Linux** / **Ubuntu 24.04**, y configurá con
   el slider algo cercano a 2 vCPU / 4 GB RAM / 40 GB SSD para arrancar
   barato -- ajustado para 5 Postgres + RabbitMQ + 6 servicios chicos, sin
   mucho margen si la carga crece. Si se siente lento, el panel de DonWeb
   deja resizear sin recrear el servidor, así que no hay que acertarle de
   entrada.
3. Si el wizard te deja cargar una clave pública SSH en la creación, usala
   (no uses solo password auth). Si DonWeb solo te da una contraseña de
   root por mail, generá tu propia clave y agregala a mano apenas entrás
   por primera vez (`ssh-copy-id root@<ip>` desde tu máquina, después
   deshabilitá el login por password en `/etc/ssh/sshd_config`).
4. Activá el firewall que ofrezca el panel de DonWeb (o `ufw` directo en el
   servidor, ver abajo) para permitir entrante solo `22` (SSH, idealmente
   restringido a tu IP), `80` y `443`. Las 5 bases y RabbitMQ nunca
   necesitan quedar expuestos a internet -- solo se hablan entre sí dentro
   de la red interna de Docker Compose.

Si el panel de DonWeb no trae firewall propio, armalo con `ufw` ya en el
servidor:

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

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
ssh-keygen -t ed25519 -C "donweb-parklink" -f ~/.ssh/id_ed25519 -N ""
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
de arrancar Caddy, si no Let's Encrypt no puede validar el dominio. Si
registraste el dominio en el propio DonWeb, el registro A se carga desde su
panel de DNS; si está en otro lado (Cloudflare, NIC.ar, etc.), desde ahí.

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
