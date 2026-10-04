# Task API — FlyRank BE-04 (Week 3, Containerize your stack)

A to-do task API built with **Python** and **FastAPI**, now backed by **PostgreSQL** running in Docker, with the full stack (app + database) started by a single `docker compose up`.

Built as part of the FlyRank Backend AI Engineering Internship — July 2026 cohort.

## What changed from BE-02

- Storage moved from SQLite (`tasks.db`, a single file) to PostgreSQL (a real database server, run as a container).
- The database connection comes from a `DATABASE_URL` environment variable, loaded from a git-ignored `.env` file. A `.env.example` with placeholder values is committed instead.
- All SQL is parameterized (`%s` placeholders via `psycopg`) — no user input is ever concatenated into a query string.
- Endpoint behavior, request/response shapes, and status codes are identical to BE-01 and BE-02. Only the storage layer changed.

## How to run it

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Start the whole stack:
   ```bash
   docker compose up
   ```

This builds the API image, starts a Postgres container with a named volume (`taskdata`) for persistence, creates the `tasks` table if it doesn't exist, and seeds three example tasks on first run only.

API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Endpoints

| Method | Path | Description | Success | Errors |
|--------|------|-------------|---------|--------|
| GET | `/` | API info | 200 | — |
| GET | `/health` | Health check (also pings the database) | 200 | — |
| GET | `/tasks` | List all tasks | 200 | — |
| GET | `/tasks/{id}` | Get a single task by id | 200 | 404 if not found |
| POST | `/tasks` | Create a new task | 201 | 400 if title missing/empty |
| PUT | `/tasks/{id}` | Update a task's title and done status | 200 | 400 invalid body, 404 if not found |
| DELETE | `/tasks/{id}` | Delete a task | 204 | 404 if not found |

## Persistence

Data is stored in the `taskdata` Docker volume, which is independent of the container's lifecycle. Running `docker compose down` followed by `docker compose up` does not lose data — only removing the volume explicitly (`docker compose down -v`) does.

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres connection string, e.g. `postgres://postgres:dev@db:5432/tasks` (service name `db` inside Docker Compose's network, or `localhost` when connecting from outside the containers) |

See `.env.example` for the exact format.

## Project files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app and all routes |
| `Dockerfile` | Builds the API's container image |
| `docker-compose.yml` | Defines the `api` and `db` services and starts them together |
| `.env.example` | Template for required environment variables (committed) |
| `.env` | Actual secrets (git-ignored, not committed) |

## Status note

This assignment's code (API, Dockerfile, docker-compose configuration, and Postgres repository logic) is complete and follows the assignment spec exactly — same endpoint behavior and status codes as BE-01/BE-02, parameterized queries, environment-based config, and a named volume for persistence.

I was not able to generate a live run screenshot for this submission because Docker Desktop could not start on this machine (BIOS virtualization support is disabled on this laptop and I was unable to change it). The code itself has not been executed against a live container in this environment. I'm submitting the implementation as-is, honestly flagged, rather than holding back a working half.
