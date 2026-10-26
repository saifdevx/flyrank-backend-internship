from fastapi import APIRouter

from src.llm.schema import TriageRequest, TriageResult
from src.llm.service import run_triage

router = APIRouter()


@router.post("/triage", response_model=TriageResult, summary="Classify a support message", tags=["triage"])
def triage(body: TriageRequest):
    return run_triage(body.text)
