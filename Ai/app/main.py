from fastapi import FastAPI
from Ai.app.api.v1.routes.health import router as health_router
from Ai.app.api.v1.routes.router import router as predict_router
from app.api import visual_router  # Vision (YOLO) router 추가

def create_app() -> FastAPI:
    app = FastAPI(title="Car-Sentry AI Server", version="1.0.0")

    # 기존 라우터
    app.include_router(health_router, prefix="/api/v1", tags=["health"])
    app.include_router(predict_router, prefix="/api/v1", tags=["predict"])
    
    # Vision (YOLO) 라우터 추가
    app.include_router(visual_router.router)

    return app

app = create_app()

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Car-Sentry AI Server is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
