from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .rate_limit import limiter
from .routers import presets, resize

# No image bytes are ever written to disk, DB, or logs: uploads are read into
# memory, processed, returned, and discarded. Uvicorn's default access log
# only records method/path/status — it does not log request/response bodies,
# so no extra scrubbing middleware is needed as long as that default stays
# untouched.
app = FastAPI(
    title="ToSpec — Exam Photo/Signature Resizer API",
    description="Server-side port of the PHOTO SPEC client-side tool, plus batch processing.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(presets.router)
app.include_router(resize.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
