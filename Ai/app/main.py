from fastapi import FastAPI
from Ai.app.api.v1.routes.health import router as health_router
from Ai.app.api.v1.routes.router import router as predict_router

def create_app() -> FastAPI:
    app = FastAPI(title="OBD AI API", version="1.0.0")

    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(predict_router, prefix="/api/v1", tags=["predict"])

    return app

app = create_app()
