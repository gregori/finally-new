from fastapi import APIRouter

from app.api._response import ok

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return ok({"status": "ok"})
