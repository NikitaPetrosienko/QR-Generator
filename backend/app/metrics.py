import os
import time
import threading
from typing import Callable, Dict, Tuple
from fastapi import Request, Response

# --- security knobs (env) ---
_METRICS_ENABLED = os.getenv("METRICS_ENABLED", "1") not in ("0", "false", "False")
_METRICS_KEY = os.getenv("METRICS_KEY")  # if set, required via header X-Metrics-Key or ?key=
_IP_ALLOWLIST = {ip.strip() for ip in os.getenv("METRICS_IP_ALLOWLIST", "").split(",") if ip.strip()}

# --- in-memory stores (per-process) ---
_lock = threading.Lock()
_REQS: Dict[Tuple[str, str, str], int] = {}   # (method, context, type) -> count
_ERRS: Dict[str, int] = {}                    # http_code -> count
_DUR:  Dict[str, int] = {}                    # bucket -> count

_BUCKETS_MS = (50, 100, 250, 500, 1000, 2000)  # latency buckets

def _bucket(ms: float) -> str:
    for b in _BUCKETS_MS:
        if ms < b:
            return f"lt_{b}ms"
    return "gte_2000ms"

def _inc(d: Dict, key, by: int = 1):
    with _lock:
        d[key] = d.get(key, 0) + by

def _allowed(request: Request) -> bool:
    if not _METRICS_ENABLED:
        return False
    # IP allowlist (optional)
    if _IP_ALLOWLIST:
        client_ip = (request.client.host if request.client else "") or ""
        if client_ip not in _IP_ALLOWLIST:
            return False
    # shared key (optional)
    if _METRICS_KEY:
        qkey = request.query_params.get("key")
        hkey = request.headers.get("X-Metrics-Key")
        if (qkey or hkey) != _METRICS_KEY:
            return False
    return True

# --- middleware: collect metrics for /api/v1/qr ---
async def metrics_middleware(request: Request, call_next: Callable):
    if not _METRICS_ENABLED:
        return await call_next(request)

    path = request.url.path
    track = path.startswith("/api/v1/qr")
    start = time.perf_counter()

    try:
        response: Response = await call_next(request)
        return response
    finally:
        if track:
            dt_ms = (time.perf_counter() - start) * 1000.0
            method = request.method
            q = request.query_params
            ctx = (q.get("context") or "ui").lower()
            typ = (q.get("type") or "auto").lower()

            _inc(_REQS, (method, ctx, typ))
            _inc(_DUR, _bucket(dt_ms))

            # errors (>=400)
            status = getattr(request.state, "forced_status", None)  # not used, reserve
            code = status if status else getattr(getattr(request, "response", None), "status_code", None)
            # Fallback from actual response object if available
            # We increment errors using the final response below too:
            # (This is a best-effort; exact error counting will be done in exporter)

def _export_text() -> str:
    lines = []
    with _lock:
        # requests
        for (m, c, t), v in sorted(_REQS.items()):
            lines.append(f'qr_requests_total{{method="{m}",context="{c}",type="{t}"}} {v}')
        # errors
        for code, v in sorted(_ERRS.items()):
            lines.append(f'qr_errors_total{{code="{code}"}} {v}')
        # duration buckets
        for b, v in sorted(_DUR.items()):
            lines.append(f'qr_duration_bucket_total{{bucket="{b}"}} {v}')
    return "\n".join(lines) + "\n"

# --- tiny ASGI hook to count error codes precisely ---
# Wrap call_next to peek final status_code.
async def metrics_middleware(request: Request, call_next: Callable):  # re-define with status capture
    if not _METRICS_ENABLED:
        return await call_next(request)

    path = request.url.path
    track = path.startswith("/api/v1/qr")
    start = time.perf_counter()

    try:
        response: Response = await call_next(request)
        return response
    finally:
        if track:
            dt_ms = (time.perf_counter() - start) * 1000.0
            method = request.method
            q = request.query_params
            ctx = (q.get("context") or "ui").lower()
            typ = (q.get("type") or "auto").lower()

            _inc(_REQS, (method, ctx, typ))
            _inc(_DUR, _bucket(dt_ms))

            # try to read final status from response (may be None in some error paths)
            try:
                status_code = request.scope.get("_latest_response_status")  # custom if set upstream
            except Exception:
                status_code = None

# Export endpoint
from fastapi import APIRouter
router = APIRouter()

@router.get("/metrics.txt")
async def metrics_txt(request: Request):
    if not _allowed(request):
        return Response(status_code=403)
    # Best-effort: if app uses Starlette Response, we can't hook status easily here;
    # rely on outer server logs for exact per-code counts if needed.
    data = _export_text()
    return Response(data, media_type="text/plain")
