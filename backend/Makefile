# Run from backend/:  make setup && make db && make run
PY=.venv/bin/python
PORT ?= 8001

setup:            ## create venv and install dependencies
	uv venv --python 3.12 .venv && uv pip install -r requirements.txt --python $(PY)

validate:         ## check content/ (ids, links, cycles, answers)
	$(PY) content/validate_content.py

db: validate      ## apply migrations and load content into SQLite
	$(PY) -m alembic upgrade head && $(PY) -m app.seed

migration:        ## after changing app/models.py: make migration m="describe change"
	$(PY) -m alembic revision --autogenerate -m "$(m)"

run:              ## start the API on http://localhost:$(PORT) (docs at /docs)
	$(PY) -m uvicorn app.main:app --reload --port $(PORT)

test:
	$(PY) -m pytest -q tests

reset:            ## delete the local database and rebuild it
	rm -f finance_quest.db* && $(MAKE) db
