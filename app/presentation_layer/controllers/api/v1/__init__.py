from fastapi import APIRouter

from app.presentation_layer.controllers.api.v1.user_router import router as user_router
from app.presentation_layer.controllers.api.v1.chat_router import router as chat_router

router = APIRouter()
router.include_router(user_router, prefix="/user", tags=["user"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])

__all__ = ["router"]
