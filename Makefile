.PHONY: up down clean

up:
	docker compose up --build --remove-orphans

down:
	docker compose down

clean:
	docker compose down -v
