.PHONY: env up local down clean qa online online-down

LOCAL_API_URL := http://localhost:8080
ONLINE_API_URL := https://gateway.parklink.com.ar

SERVICES := auth-service booking-service gateway notifications-service parking-service payment-service

# Crea el .env de cada microservicio desde su .env.example, solo si todavía no existe.
env:
	@for s in $(SERVICES); do [ -f $$s/.env ] || { cp $$s/.env.example $$s/.env && echo "[$$s] .env creado: completá sus claves"; }; done

up: env
	@# Solo en la máquina con el modo online: deja mobile y admin apuntando a la API local.
	@if [ -f compose.cloudflare.yaml ]; then ./scripts/set-api-url.sh $(LOCAL_API_URL); fi
	docker compose up --build --remove-orphans

# Como `up`, pero mobile y admin apuntan a la IP de esta compu en la red local
# (http://192.168.x.x:8080), así la app anda desde un celular conectado al mismo wifi.
# La IP es la de la interfaz por la que sale el tráfico (Linux); en macOS, la de en0.
LAN_IP = $(shell ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($$i=="src") {print $$(i+1); exit}}' || true)

local: env
	@ip="$(LAN_IP)"; [ -n "$$ip" ] || ip="$$(ipconfig getifaddr en0 2>/dev/null)"; \
	  [ -n "$$ip" ] || { echo "No pude detectar la IP de la red local."; exit 1; }; \
	  ./scripts/set-api-url.sh "http://$$ip:8080"
	docker compose up --build --remove-orphans

down:
	docker-compose down

clean:
	docker compose down -v

qa:
	./scripts/qa_test.sh

# Todo online con Cloudflare Tunnel (gateway.parklink.com.ar y expo.parklink.com.ar).
# compose.cloudflare.yaml es local y no está en el repo; los tokens de los túneles van en .env.
ONLINE_COMPOSE := compose.cloudflare.yaml

online: env
	@test -f $(ONLINE_COMPOSE) || { echo "Falta $(ONLINE_COMPOSE) (no está en el repo)."; exit 1; }
	./scripts/set-api-url.sh $(ONLINE_API_URL)
	docker compose -f $(ONLINE_COMPOSE) up --build --remove-orphans

online-down:
	@test -f $(ONLINE_COMPOSE) || { echo "Falta $(ONLINE_COMPOSE) (no está en el repo)."; exit 1; }
	docker compose -f $(ONLINE_COMPOSE) down
