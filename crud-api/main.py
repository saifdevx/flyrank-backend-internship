from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel

app = FastAPI()

tasks = [
    {"id": 1, "title": "Buy milk", "done": False},
    {"id": 2, "title": "Walk the dog", "done": False},
    {"id": 3, "title": "Finish assignment", "done": True},
]

@app.get("/", summary="API info")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}

@app.get("/health", summary="Health check")
def health():
    return {"status": "ok"}

@app.get("/tasks", summary="List all tasks")
def get_tasks():
    return tasks



@app.get("/tasks/{id}", summary="Get a single task by id")
def get_task(id: int):
    for task in tasks:
        if task["id"] == id:
            return task
    raise HTTPException(status_code=404, detail=f"Task {id} not found")

class TaskCreate(BaseModel):
    title: str

@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(task: TaskCreate):
    if not task.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    
    new_id = max((t["id"] for t in tasks), default=0) + 1
    new_task = {"id": new_id, "title": task.title, "done": False}
    tasks.append(new_task)
    return new_task



class TaskUpdate(BaseModel):
    title: str
    done: bool

@app.put("/tasks/{id}", summary="Update a task")
def update_task(id: int, updated: TaskUpdate):
    if not updated.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    
    for task in tasks:
        if task["id"] == id:
            task["title"] = updated.title
            task["done"] = updated.done
            return task
    raise HTTPException(status_code=404, detail=f"Task {id} not found")


@app.delete("/tasks/{id}", status_code=204, summary="Delete a task")
def delete_task(id: int):
    for task in tasks:
        if task["id"] == id:
            tasks.remove(task)
            return
    raise HTTPException(status_code=404, detail=f"Task {id} not found")