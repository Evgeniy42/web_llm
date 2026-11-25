from fastapi import APIRouter

from app.presentation_layer.controllers.health import router as health_router
from app.presentation_layer.controllers.api import router as api_router

router = APIRouter()
router.include_router(health_router, prefix="/api")
router.include_router(api_router, prefix="/api")

__all__ = ['router']
