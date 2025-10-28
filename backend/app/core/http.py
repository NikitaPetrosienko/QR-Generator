# backend/app/core/http.py
from fastapi import Request, Response
import hashlib, re, unicodedata, urllib.parse

def _safe_ascii_filename(name: str, default: str = "qr_code") -> str:
    base = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._-")
    return base or default

def respond_png(request: Request, *, data_key: str, content: bytes, filename: str) -> Response:
    etag = hashlib.sha256(data_key.encode("utf-8")).hexdigest()

    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)

    ascii_name = _safe_ascii_filename(filename) + ".png"
    utf8_name = urllib.parse.quote((filename or "qr_code") + ".png", safe="")

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}',
    }
    return Response(content=content, media_type="image/png", headers=headers)
