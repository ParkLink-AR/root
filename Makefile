.PHONY: up down clean qa

up:
	docker compose up --build --remove-orphans

down:
	docker-compose down

clean:
	docker compose down -v

qa:
	./scripts/qa_test.sh
