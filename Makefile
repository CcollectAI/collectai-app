VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: venv deps test lint

venv:
	@test -x $(PY) || python3 -m venv $(VENV)

deps: venv
	$(PIP) install --upgrade pip
	$(PIP) install --constraint constraints.txt -r requirements.txt -r requirements-dev.txt

test:
	$(PY) -m pytest -q

lint:
	@command -v ruff >/dev/null 2>&1 && ruff check server/ || echo "[lint] ruff not installed — skipping python lint"
	@npx --yes tsc --noEmit
