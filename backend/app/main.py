from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.routers import api_keys as api_keys_router
from app.routers import auth as auth_router
from app.routers import catalog as catalog_router
from app.routers import jobs as jobs_router
from app.routers import validation as validation_router

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="SynthRare API",
    description="Synthetic rare data generation platform",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", settings.next_public_app_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router.router)
app.include_router(catalog_router.router)
app.include_router(jobs_router.router)
app.include_router(validation_router.router)
app.include_router(api_keys_router.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


@app.get("/files/{file_path:path}")
def serve_local_file(file_path: str) -> FileResponse:
    """Serve files from local storage (dev/local mode only)."""
    if not settings.use_local_storage:
        raise HTTPException(status_code=404, detail="Local file serving is disabled")
    from pathlib import Path
    full_path = Path(settings.local_storage_path) / file_path.lstrip("/")
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Prevent path traversal
    try:
        full_path.resolve().relative_to(Path(settings.local_storage_path).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(str(full_path))
