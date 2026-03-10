from fastapi import APIRouter

from app.repo import check_connectivity, check_lancedb_connectivity

router = APIRouter()


@router.get("/health")
async def health():
    b2_ok = check_connectivity()
    lancedb_ok = check_lancedb_connectivity()
    all_ok = b2_ok and lancedb_ok
    return {
        "status": "healthy" if all_ok else "degraded",
        "b2_connected": b2_ok,
        "lancedb_connected": lancedb_ok,
    }
