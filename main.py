import uvicorn

from app.configuration.application_factory import create_app
from app.configuration.settings import Settings

app = create_app()

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
