.PHONY: install migrate seed test dev run clean

PYTHON = backend/.venv/Scripts/python.exe
PYTEST = backend/.venv/Scripts/pytest.exe

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

migrate:
	cd backend && $(PYTHON) -m alembic upgrade head

seed:
	cd backend && $(PYTHON) -m app.core.seed_bhms

test:
	$(PYTEST) backend/tests -v

dev:
	start cmd /k "cd backend && $(PYTHON) -m uvicorn app.main:app --reload --port 8000"
	start cmd /k "cd frontend && npm run dev"

run:
	docker-compose up -d --build

reset-db:
	cd backend && $(PYTHON) -m app.core.reset_database --all

