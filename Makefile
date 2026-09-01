.PHONY: test frontend-test lint

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest -q

frontend-test:
	cd frontend && npm test

lint:
	cd frontend && npm run lint
