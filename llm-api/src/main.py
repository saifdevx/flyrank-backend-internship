from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.llm import config  # noqa: F401  (loads .env)
from src.llm.client import LLMError
from src.routes.triage import router

app = FastAPI(title="Support Triage API",
              description="One endpoint: POST /triage classifies a support message with an LLM and returns validated JSON.")
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def bad_input(request: Request, exc: RequestValidationError):
    """Bad input is a 400 that names the field, and no model call was made."""
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if p != "body"]
        name = ".".join(loc)
        if not name or name.isdigit():      # e.g. a body that is not JSON at all
            name = "body"
        fields.append({"field": name, "message": err["msg"]})
    return JSONResponse(status_code=400, content={"error": "Invalid input", "fields": fields})


@app.exception_handler(LLMError)
async def llm_failed(request: Request, exc: LLMError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.get("/health", summary="Health check", tags=["meta"])
def health():
    return {"status": "ok"}
