# Task API — FlyRank BE-01 (Week 2)

A simple to-do task API built with **Python** and **FastAPI**. Supports full CRUD (Create, Read, Update, Delete) on an in-memory list of tasks, with interactive Swagger UI docs.

Built as part of the FlyRank Backend AI Engineering Internship — July 2026 cohort.

## How to run it

From inside the `week2-crud-api` folder:

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install fastapi uvicorn
uvicorn main:app --reload
```

Server runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Endpoints

| Method | Path | Description | Success | Errors |
|--------|------|-------------|---------|--------|
| GET | `/` | API info | 200 | — |
| GET | `/health` | Health check | 200 | — |
| GET | `/tasks` | List all tasks | 200 | — |
| GET | `/tasks/{id}` | Get a single task by id | 200 | 404 if not found |
| POST | `/tasks` | Create a new task | 201 | 400 if title missing/empty |
| PUT | `/tasks/{id}` | Update a task's title and done status | 200 | 400 invalid body, 404 if not found |
| DELETE | `/tasks/{id}` | Delete a task | 204 | 404 if not found |

## Example request

```
curl.exe -i http://localhost:8000/tasks/1
```

Response:

```
HTTP/1.1 200 OK
date: Sat, 18 Jul 2026 06:53:21 GMT
server: uvicorn
content-length: 40
content-type: application/json

{"id":1,"title":"Buy milk","done":false}
```

## Swagger UI

All endpoints tested and working via `/docs` — full CRUD cycle (create, list, update, delete) confirmed with "Try it out."

![Swagger UI screenshot](swagger-screenshot.png)!

## Notes

Data is stored in memory (a Python list) — it resets every time the server restarts. This is intentional for this stage; a real database is introduced in Week 3.
