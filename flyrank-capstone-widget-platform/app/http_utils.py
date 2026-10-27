from . import config
from .errors import BadRequest, PayloadTooLarge


def client_ip(request):
    if config.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def read_body_capped(request, limit):
    """Read the body but refuse to hold more than `limit` bytes in memory."""
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            size = int(declared)
        except ValueError:
            raise BadRequest("Invalid Content-Length header")
        if size > limit:
            raise PayloadTooLarge(f"Payload too large (max {limit} bytes)")
    chunks, total = [], 0
    async for chunk in request.stream():     # also covers requests with no Content-Length
        total += len(chunk)
        if total > limit:
            raise PayloadTooLarge(f"Payload too large (max {limit} bytes)")
        chunks.append(chunk)
    return b"".join(chunks)
