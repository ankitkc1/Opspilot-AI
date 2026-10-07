# OpsPilot AI

OpsPilot is a local-first operations system for small businesses. The current core release manages products, inventory, and sales, then turns that data into a daily operating dashboard.

## Core features

- Secure account login and user administration
- Product catalog with pricing and inventory policy
- Inventory balances and stock movement history
- Sales recording with automatic stock deductions
- Daily revenue, sales, top-product, and low-stock dashboard
- Local Ollama connectivity and model-readiness checks
- PostgreSQL migrations and automated backend tests

The local AI foundation uses Ollama with `qwen3:4b`. Business-facing AI workflows
will build on this tested service layer in later milestones.

## Architecture

- `backend/app/models.py` contains the database and API data models.
- `backend/app/api/routes/` contains the FastAPI endpoints.
- `backend/app/services/` contains reusable business rules.
- `backend/app/alembic/versions/` contains database migrations.
- `backend/tests/` contains backend tests.
- `frontend/src/routes/_layout/` contains the main React pages.
- `frontend/src/components/` contains shared UI components.
- `frontend/src/client/` is generated from the backend OpenAPI schema.

## Run with Docker

From the project root:

```powershell
docker compose run --rm backend bash scripts/prestart.sh
docker compose up --build
```

Then open:

- Application: <http://localhost:8000>
- API documentation: <http://localhost:8000/docs>
- Database admin: <http://localhost:8080>
- Development email inbox: <http://localhost:8025>

The `changethis` warnings are acceptable only for local development. Replace those values in `.env` before any deployment.

## Local AI

Install Ollama on the host machine and download the configured model once:

```powershell
ollama pull qwen3:4b
ollama list
```

When the backend runs in Docker, it reaches host Ollama through
`host.docker.internal`. When the backend runs directly on the host, it defaults to
`http://localhost:11434`. These defaults can be changed with
`OLLAMA_DOCKER_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_TIMEOUT_SECONDS`.

After signing in, check `GET /api/v1/ai/status` in the API documentation. It
reports `ready`, `model_missing`, or `unavailable`. Automated tests use a mocked
Ollama transport, so Ollama does not need to be running during the test suite.

## Quality checks

Backend:

```powershell
cd backend
uv run ruff check app tests
uv run mypy app tests
uv run pytest
```

Frontend:

```powershell
cd frontend
bun install
bun run build
```

## Additional documentation

- [Backend development](backend/README.md)
- [Frontend development](frontend/README.md)
- [Local development](development.md)
- [Docker deployment](deployment-docker-compose.md)

## License

This project retains the MIT license from its original FastAPI full-stack template foundation.
