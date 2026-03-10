import json
import logging
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

from app.config import settings  # noqa: E402
from app.repo import check_connectivity, check_lancedb_connectivity  # noqa: E402
from app.runtime import chat, dashboard, documents, files, health, metrics, upload  # noqa: E402

# --- Structured JSON logging ---

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
# Quiet noisy libraries
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("api")


# --- Startup checks ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup checks for external dependencies."""
    b2_ok = check_connectivity()
    lancedb_ok = check_lancedb_connectivity()
    if b2_ok:
        logger.info("B2 connectivity check passed")
    else:
        logger.error("B2 connectivity check FAILED — uploads and file ops will not work")
    if lancedb_ok:
        logger.info("LanceDB connectivity check passed")
    else:
        logger.warning("LanceDB connectivity check failed — vector search unavailable until first ingestion")
    yield


# --- App setup ---

app = FastAPI(
    title="Agentic RAG Vector Starter Kit API",
    description="Agentic RAG pipeline backed by Backblaze B2 and LanceDB",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Request ID + timing middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=metrics.timing_middleware)

app.include_router(health.router, tags=["health"])
app.include_router(upload.router, tags=["upload"])
app.include_router(files.router, tags=["files"])
app.include_router(documents.router, tags=["documents"])
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(metrics.router, tags=["metrics"])
