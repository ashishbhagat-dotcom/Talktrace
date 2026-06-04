.PHONY: up down build migrate makemigrations shell test seed logs worker-logs createsuperuser reindex lint format

# ─── Docker ───────────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

restart:
	docker compose restart django celery-worker celery-beat

# ─── Database ─────────────────────────────────────────────────────────────────
migrate:
	docker compose exec django python manage.py migrate

makemigrations:
	docker compose exec django python manage.py makemigrations

# ─── Development ──────────────────────────────────────────────────────────────
shell:
	docker compose exec django python manage.py shell

createsuperuser:
	docker compose exec django python manage.py createsuperuser

seed:
	docker compose exec django python manage.py seed_demo_data

reindex:
	docker compose exec django python manage.py reindex_elasticsearch

# ─── Testing ──────────────────────────────────────────────────────────────────
test:
	docker compose exec django pytest

test-v:
	docker compose exec django pytest -v

test-cov:
	docker compose exec django pytest --cov=apps --cov-report=term-missing

# ─── Logs ─────────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f

django-logs:
	docker compose logs -f django

worker-logs:
	docker compose logs -f celery-worker

beat-logs:
	docker compose logs -f celery-beat

# ─── Code quality ─────────────────────────────────────────────────────────────
lint:
	docker compose exec django flake8 apps/ config/

format:
	docker compose exec django black apps/ config/ && docker compose exec django isort apps/ config/

# ─── Shortcuts ────────────────────────────────────────────────────────────────
ps:
	docker compose ps

stop:
	docker compose stop
