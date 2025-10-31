import time, logging
from fastapi import Request

logger = logging.getLogger("qr")

async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        dur_ms = round((time.perf_counter() - start) * 1000, 2)
        path = request.url.path
        q_type = request.query_params.get("type", "vcard")
        source = "portal" if "X-Employee-Fn" in request.headers else "manual"
        logger.info(
            "qr_request",
            extra={"kv": {
                "event": "qr_request",
                "type": q_type,
                "from": source,
                "path": path,
                "status": status,
                "ms": dur_ms
            }},
        )
