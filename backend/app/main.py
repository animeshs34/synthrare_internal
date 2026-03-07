from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
