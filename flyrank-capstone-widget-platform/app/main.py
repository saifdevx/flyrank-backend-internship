import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, cors, db, jobs
from .errors import AppError
from .routes import admin, public

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app):
    db.migrate()                                   # schema is created/updated on every start
    worker = None
    if config.WORKER_ENABLED:
        worker = jobs.Worker()
        worker.start()
    yield
    if worker:
        worker.stop()


app = FastAPI(
    title="Embeddable Widget & Lead-Capture Platform",
    description="Owners create widgets and get a one-line <script> snippet. Visitors submit forms from any website; "
                "submissions are validated, rate-limited, spam-filtered, geo-enriched, stored and shown in a dashboard.",
    lifespan=lifespan,
)
app.middleware("http")(cors.cors_middleware)
app.include_router(public.router)
app.include_router(admin.router)
if config.DEV_TOOLS:
    from .routes import dev
    app.include_router(dev.router)


def _error(status, message, headers=None, fields=None):
    body = {"error": message}
    if fields:
        body["fields"] = fields
    return JSONResponse(body, status_code=status, headers=headers)


@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError):
    return _error(exc.status_code, exc.message, exc.headers, exc.fields)


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, exc: RequestValidationError):
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
        name = ".".join(loc)
        fields.append({"field": "body" if not name or name.isdigit() else name, "message": err["msg"]})
    return _error(400, "Invalid input", fields=fields)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, str(exc.detail), getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    logging.getLogger("app").exception("unhandled error")     # details go to the log, never to the caller
    return _error(500, "Internal server error")


@app.get("/health", tags=["meta"], summary="Health check")
def health():
    return {"status": "ok"}
