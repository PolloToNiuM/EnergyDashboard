.PHONY: help backend-install backend-run frontend-run

help:
	@echo "Available commands:"
	@echo "  make backend-install  Install backend dependencies in the local virtualenv"
	@echo "  make backend-run      Run the FastAPI backend on http://127.0.0.1:8000"
	@echo "  make frontend-run     Run the Vue frontend on http://127.0.0.1:5173"

backend-install:
	./backend/.venv/bin/pip install -e ./backend

backend-run:
	./backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload

frontend-run:
	./frontend/node_modules/.bin/vite frontend --host 0.0.0.0 --port 5173
