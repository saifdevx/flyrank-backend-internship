"""Dev-only switches to PROVE failure handling. Mounted only when DEV_TOOLS=1. Never enable this in production."""
from fastapi import APIRouter

from .. import dev_state, jobs
from ..schemas import TogglesIn

router = APIRouter(prefix="/dev", tags=["dev (DEV_TOOLS=1 only)"])


@router.get("/toggles", summary="Current failure switches")
def get_toggles():
    return dev_state.get()


@router.post("/toggles", summary="Take geo provider A/B down, or make email fail")
def set_toggles(body: TogglesIn):
    return dev_state.update(body.model_dump())


@router.post("/jobs/run", summary="Run all due background jobs now")
def run_jobs():
    processed = 0
    while jobs.process_one() and processed < 100:
        processed += 1
    return {"processed": processed}
