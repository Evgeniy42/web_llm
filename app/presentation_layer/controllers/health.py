from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
def health():
    """Простая проверка жизни процесса."""
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(request: Request):
    """Проверка готовности: доступность PostgreSQL."""
    try:
        async with request.app.state.db_manager.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready"},
        )
