.PHONY: setup seed enrich index evaluate test preflight smoke product-images dev-api dev-web
setup:
	cd backend && uv sync --frozen
	cd frontend && npm ci
seed enrich index evaluate preflight:
	cd backend && uv run --frozen python -m app.cli $@
smoke:
	cd backend && uv run --frozen python -m app.cli smoke --image
product-images:
	cd backend && DEMO_MODE=live uv run --frozen python -m app.cli product-images
test:
	cd backend && uv run --frozen pytest -q
	cd frontend && npm run typecheck && npm run lint
dev-api:
	mkdir -p data/runtime
	cd backend && uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 2>&1 | tee -a ../data/runtime/api.log
dev-web:
	cd frontend && npm run dev -- --hostname 127.0.0.1
