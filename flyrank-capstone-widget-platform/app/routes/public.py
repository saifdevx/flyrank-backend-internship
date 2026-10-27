"""HTTP layer for the open internet: widget script, widget config, submissions. Everything here is untrusted input."""
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from .. import bundle, config, rate_limit, services
from ..errors import BadRequest, RateLimited
from ..http_utils import client_ip, read_body_capped

router = APIRouter()

SCRIPT_HEADERS = {"X-Content-Type-Options": "nosniff"}


def _script(max_age_header):
    etag = f'"{bundle.VERSION}"'
    return Response(content=bundle.BYTES, media_type="application/javascript",
                    headers={**SCRIPT_HEADERS, "Cache-Control": max_age_header, "ETag": etag})


@router.api_route("/widget.js", methods=["GET", "HEAD"], tags=["public"], summary="Widget script (short cache; use the versioned URL in production)")
def widget_js():
    return _script("public, max-age=300")


@router.api_route("/widget.{version}.js", methods=["GET", "HEAD"], tags=["public"], summary="Versioned widget script (cached for a year)")
def widget_versioned(version: str):
    if version == bundle.VERSION:
        # content hash is in the URL, so this exact URL can never change: cache it "forever"
        return _script("public, max-age=31536000, immutable")
    return _script("public, max-age=300")        # an old version in an old snippet still works, but is not cached long


@router.api_route("/widgets/{widget_id}/config", methods=["GET", "HEAD"], tags=["public"], summary="Public widget configuration (cached 60s)")
def widget_config(widget_id: str, request: Request):
    cfg = services.public_config(widget_id)
    etag = '"' + hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16] + '"'
    headers = {"Cache-Control": f"public, max-age={config.CONFIG_MAX_AGE}", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(cfg, headers=headers)


@router.post("/submissions", tags=["public"], summary="Submit a widget form (public, CORS, rate-limited)")
async def submit(request: Request, idempotency_key: Optional[str] = Header(default=None)):
    ip = client_ip(request)
    allowed, retry = rate_limit.limiter.consume(f"ip:{ip}", config.RATE_IP_BURST, config.RATE_IP_REFILL_PER_SEC)
    if not allowed:
        raise RateLimited(retry)                                   # cheapest check first: shed floods early
    body = await read_body_capped(request, config.MAX_BODY_BYTES)  # 413 if too big
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise BadRequest("Body must be valid JSON")
    services.check_idempotency_key(idempotency_key)
    result = await run_in_threadpool(services.submit, payload, ip, idempotency_key)
    if result == "duplicate":
        return JSONResponse({"status": "received", "duplicate": True}, status_code=200)
    return JSONResponse({"status": "received"}, status_code=201)   # spam gets the same answer as a real submit
