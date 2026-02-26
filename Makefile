.PHONY: infra infra-down up down dev migrate index shell logs help

help:
	@echo ""
	@echo "  make infra      — Khởi động PostgreSQL + Elasticsearch (dành cho dev local)"
	@echo "  make infra-down — Dừng PostgreSQL + Elasticsearch"
	@echo "  make up         — Khởi động toàn bộ stack kể cả App (production)"
	@echo "  make down       — Dừng toàn bộ stack"
	@echo "  make dev        — Chạy API server dev (hot-reload, cần infra đang chạy)"
	@echo "  make migrate    — Tạo bảng PostgreSQL"
	@echo "  make index      — Chạy offline job: PG → Elasticsearch"
	@echo "  make logs       — Xem logs của app container"
	@echo "  make shell      — Mở Python REPL với DB session"
	@echo ""

# Chỉ khởi động DB services (dùng khi dev local với `make dev`)
infra:
	docker compose up -d postgres elasticsearch

infra-down:
	docker compose stop postgres elasticsearch

# Khởi động toàn bộ stack (app chạy trong container)
up:
	docker compose --profile full up -d --build

down:
	docker compose --profile full down

# Chạy dev server local (yêu cầu `make infra` trước)
dev:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Tạo bảng PostgreSQL từ SQLAlchemy models
migrate:
	python -c "from src.core.database import engine; from src.models import *; from src.core.database import Base; Base.metadata.create_all(bind=engine); print('✓ Tables created.')"

# Chạy offline indexing job
index:
	python -m jobs.ingest_pipeline

# Xem logs app
logs:
	docker compose logs -f app

shell:
	python -i -c "from src.core.database import SessionLocal; db = SessionLocal(); print('db ready')"
