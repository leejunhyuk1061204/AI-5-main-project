from fastapi import APIRouter

from ai.app.api.v1.routes.health import router as health_router
from ai.app.api.v1.routes.anomaly import router as anomaly_router
from ai.app.api.v1.routes.wear_factor import router as wear_factor_router
from ai.app.api.v1.routes.visual_router import router as visual_router


router = APIRouter()

router.include_router(health_router)
router.include_router(anomaly_router)
router.include_router(wear_factor_router)
router.include_router(visual_router)
