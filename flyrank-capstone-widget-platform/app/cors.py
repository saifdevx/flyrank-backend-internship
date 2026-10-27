"""CORS for the PUBLIC paths only. The admin API deliberately gets no CORS headers."""
import re

from fastapi import Request
from fastapi.responses import Response

PUBLIC_PATHS = [
    re.compile(r"^/submissions$"),
    re.compile(r"^/widgets/[^/]+/config$"),
    re.compile(r"^/widget(\.[A-Za-z0-9]+)?\.js$"),
]


def is_public(path):
    return any(p.match(path) for p in PUBLIC_PATHS)


def _headers(preflight):
    headers = {
        "Access-Control-Allow-Origin": "*",          # any customer site may embed the widget; no cookies are used
        "Access-Control-Expose-Headers": "Retry-After, ETag",
    }
    if preflight:
        headers.update({
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Idempotency-Key",
            "Access-Control-Max-Age": "600",
        })
    return headers


async def cors_middleware(request: Request, call_next):
    public = is_public(request.url.path)
    if public and request.method == "OPTIONS":
        return Response(status_code=204, headers=_headers(preflight=True))   # answer the preflight ourselves
    response = await call_next(request)
    if public:
        response.headers.update(_headers(preflight=False))
    return response
