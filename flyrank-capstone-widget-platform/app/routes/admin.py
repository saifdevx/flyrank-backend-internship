"""HTTP layer for the owner: sign up, manage widgets, read the dashboard. Thin on purpose."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from .. import config, rate_limit, services
from ..errors import RateLimited
from ..http_utils import client_ip
from ..schemas import TenantIn, WidgetIn
from ..security import bearer, current_tenant

router = APIRouter(prefix="/admin")


@router.post("/tenants", status_code=201, tags=["signup"], summary="Create an account and get an API key")
def signup(body: TenantIn, request: Request):
    allowed, retry = rate_limit.limiter.consume(f"signup:{client_ip(request)}", config.RATE_SIGNUP_BURST, config.RATE_SIGNUP_REFILL_PER_SEC)
    if not allowed:
        raise RateLimited(retry)
    tenant_id, api_key = services.create_tenant(body.name, body.email)
    return {"tenant_id": tenant_id, "email": body.email, "api_key": api_key,
            "note": "Store this key now. It is shown once; only a hash is kept."}


@router.post("/widgets", status_code=201, tags=["widgets"], summary="Create a widget")
def create_widget(body: WidgetIn, tenant=Depends(current_tenant)):
    return services.create_widget(tenant["id"], body)


@router.get("/widgets", tags=["widgets"], summary="List my widgets")
def list_widgets(tenant=Depends(current_tenant)):
    return services.list_widgets(tenant["id"])


@router.get("/widgets/{widget_id}", tags=["widgets"], summary="Get one of my widgets")
def get_widget(widget_id: str, tenant=Depends(current_tenant)):
    return services.get_widget(tenant["id"], widget_id)


@router.put("/widgets/{widget_id}", tags=["widgets"], summary="Replace a widget's settings")
def update_widget(widget_id: str, body: WidgetIn, tenant=Depends(current_tenant)):
    return services.update_widget(tenant["id"], widget_id, body)


@router.delete("/widgets/{widget_id}", status_code=204, tags=["widgets"], summary="Delete a widget and its submissions")
def delete_widget(widget_id: str, tenant=Depends(current_tenant)):
    services.delete_widget(tenant["id"], widget_id)
    return Response(status_code=204)


@router.get("/widgets/{widget_id}/embed", tags=["widgets"], summary="Get the one-line <script> snippet")
def embed(widget_id: str, tenant=Depends(current_tenant)):
    return services.embed_snippet(tenant["id"], widget_id)


@router.get("/submissions", tags=["dashboard"], summary="List my submissions")
def submissions(widget_id: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                tenant=Depends(current_tenant)):
    return services.list_submissions(tenant["id"], widget_id, limit, offset)


@router.get("/stats", tags=["dashboard"], summary="Counts over time, per widget, and by country")
def stats(tenant=Depends(current_tenant)):
    return services.stats(tenant["id"])
