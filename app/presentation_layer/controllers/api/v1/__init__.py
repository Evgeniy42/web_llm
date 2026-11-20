from fastapi import APIRouter

from app.presentation_layer.controllers.api.v1.chat_router import router as chat_router
from app.presentation_layer.controllers.api.v1.rag_router import router as rag_router
from app.presentation_layer.controllers.api.v1.user_router import router as user_router

router = APIRouter()
router.include_router(user_router, prefix="/user", tags=["user"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(rag_router, prefix="/rag", tags=["rag"])

__all__ = ["router"]
