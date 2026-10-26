from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health():
    """Простая проверка жизни процесса."""
    return {"status": "alive"}


@router.get("/health/ready")
def health_ready(request: Request):
    """Проверка готовности: доступность PostgreSQL."""
    try:
        with request.app.state.db_manager.engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready"},
        )
