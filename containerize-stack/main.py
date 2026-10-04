import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()


def get_db():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    count = conn.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]
    if count == 0:
        conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Buy milk", False))
        conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Walk the dog", False))
        conn.execute("INSERT INTO tasks (title, done) VALUES (%s, %s)", ("Finish assignment", True))
    conn.commit()
    conn.close()


init_db()


@app.get("/", summary="API info")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Health check")
def health():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "ok", "db": "ok"}
    except Exception:
        return {"status": "ok", "db": "unreachable"}


@app.get("/tasks", summary="List all tasks")
def get_tasks():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks").fetchall()
    conn.close()
    return rows


@app.get("/tasks/{id}", summary="Get a single task by id")
def get_task(id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = %s", (id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {id} not found")
    return row


class TaskCreate(BaseModel):
    title: str


@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(task: TaskCreate):
    if not task.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    conn = get_db()
    row = conn.execute(
        "INSERT INTO tasks (title, done) VALUES (%s, %s) RETURNING *",
        (task.title, False)
    ).fetchone()
    conn.commit()
    conn.close()
    return row


class TaskUpdate(BaseModel):
    title: str
    done: bool


@app.put("/tasks/{id}", summary="Update a task")
def update_task(id: int, updated: TaskUpdate):
    if not updated.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    conn = get_db()
    row = conn.execute(
        "UPDATE tasks SET title = %s, done = %s WHERE id = %s RETURNING *",
        (updated.title, updated.done, id)
    ).fetchone()
    conn.commit()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {id} not found")
    return row


@app.delete("/tasks/{id}", status_code=204, summary="Delete a task")
def delete_task(id: int):
    conn = get_db()
    cursor = conn.execute("DELETE FROM tasks WHERE id = %s", (id,))
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Task {id} not found")
    return
