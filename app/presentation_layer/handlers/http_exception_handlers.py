import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.application_layer.contracts.client_contracts.docling_protocol import DoclingError
from app.application_layer.contracts.client_contracts.embedding_protocol import EmbeddingError
from app.application_layer.contracts.client_contracts.keycloak_protocol import KeycloakError
from app.application_layer.contracts.client_contracts.llm_protocol import LLMError
from app.application_layer.contracts.client_contracts.qdrant_protocol import QdrantError
from app.application_layer.services.retrieval_service import RetrievalError
from app.application_layer.services.user_service import (
    InvalidCredentialsError,
    UserNotFoundError,
)
from app.presentation_layer.dto.embedding_dto import INGEST_ERROR_MESSAGE, IngestResponseDTO

logger = logging.getLogger(__name__)


async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def keycloak_error_handler(request: Request, exc: KeycloakError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"Ошибка сервиса аутентификации: {exc}"},
    )


async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    """LLM-сервис недоступен, отклонил токен или вернул пустой ответ."""
    logger.exception("Ошибка языковой модели при обработке %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"Ошибка языковой модели: {exc}"},
    )


async def retrieval_error_handler(request: Request, exc: RetrievalError) -> JSONResponse:
    """Поиск контекста в чате недоступен (эмбеддинги или Qdrant)."""
    logger.exception("Ошибка поиска контекста при обработке %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"Ошибка поиска по документам: {exc}"},
    )


async def rag_error_handler(request: Request, exc: DoclingError | EmbeddingError | QdrantError) -> JSONResponse:
    """Ошибки конвейера загрузки документа: конвертация, эмбеддинги, Qdrant.

    Ответ остаётся в контракте IngestResponseDTO (success=False и
    стандартное сообщение) — клиент всегда парсит одну и ту же форму,
    детали ошибки остаются в логах сервера.
    """
    logger.exception("Ошибка конвейера загрузки документа: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=IngestResponseDTO(
            success=False,
            message=INGEST_ERROR_MESSAGE,
        ).model_dump(),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(UserNotFoundError, user_not_found_handler)
    app.add_exception_handler(InvalidCredentialsError, invalid_credentials_handler)
    app.add_exception_handler(KeycloakError, keycloak_error_handler)
    app.add_exception_handler(LLMError, llm_error_handler)
    app.add_exception_handler(RetrievalError, retrieval_error_handler)
    app.add_exception_handler(DoclingError, rag_error_handler)
    app.add_exception_handler(EmbeddingError, rag_error_handler)
    app.add_exception_handler(QdrantError, rag_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
