.PHONY: install run test lint typecheck

install:
	pip install -r requirements-dev.txt

run:
	uvicorn backend.app.main:app --reload

test:
	DEV_MOCK_AI=true JOBS_SYNC=true pytest

lint:
	ruff check --select F backend/ vision/ palmistry/

typecheck:
	npm run typecheck
