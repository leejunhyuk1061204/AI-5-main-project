from fastapi import APIRouter

from Ai.app.api_v1.routes.health import router as health_router
from Ai.app.api_v1.routes.anomaly import router as anomaly_router
from Ai.app.api_v1.routes.wear_factor import router as wear_factor_router
from Ai.app.api_v1.routes.visual_router import router as visual_router  # 네 프로젝트에 이미 있으면

router = APIRouter()

router.include_router(health_router)
router.include_router(anomaly_router)
router.include_router(wear_factor_router)
router.include_router(visual_router)
