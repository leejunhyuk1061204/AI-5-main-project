
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from ai.app.services.visual.visual_service import get_smart_visual_diagnosis
from ai.app.services.visual.router_service import SceneType
from ai.app.schemas.visual_schema import VisualResponse

async def verify_router_fallback():
    print("\n--- [Test 1] Router Low Confidence Fallback ---")
    mock_router = MagicMock()
    mock_router.classify = AsyncMock(return_value=(SceneType.SCENE_EXTERIOR, 0.35)) # Below 0.4
    
    mock_llm = AsyncMock(return_value=VisualResponse(
        status="WARNING",
        analysis_type="LLM_FALLBACK",
        category="EXTERIOR",
        data={}
    ))
    
    with patch('ai.app.services.visual.visual_service.analyze_general_image', mock_llm), \
         patch('ai.app.services.visual.visual_service._safe_load_image', AsyncMock(return_value=(MagicMock(), b"bytes", []))):
        
        result = await get_smart_visual_diagnosis("s3://test/img.jpg", models={"router": mock_router})
        
        print(f"Result Analysis Type: {result.get('analysis_type')}")
        assert result.get("analysis_type") == "SCENE_EXTERIOR" # Mapped from category
        mock_llm.assert_called_once()
        print("✅ Router Fallback Passed")

async def verify_dashboard_miss_fallback():
    print("\n--- [Test 2] Dashboard Gate 0 (MISS) Fallback ---")
    from ai.app.services.visual.domains.dashboard_service import analyze_dashboard_image
    
    mock_yolo = MagicMock()
    mock_yolo.predict.return_value = [] # No detections
    
    mock_llm_general = AsyncMock(return_value=VisualResponse(status="CRITICAL", analysis_type="LLM", category="DASHBOARD", data={}))
    mock_llm_label = AsyncMock(return_value={"labels": [{"part": "check_engine", "bbox": [0.1, 0.1, 0.2, 0.2]}], "status": "CRITICAL"})
    
    with patch('ai.app.services.visual.domains.dashboard_service.analyze_general_image', mock_llm_general), \
         patch('ai.app.services.visual.domains.dashboard_service._run_llm_labeling_for_miss', AsyncMock(return_value=[{"label": "check_engine"}])):
        
        image = MagicMock()
        image.width, image.height = 1000, 1000
        result = await analyze_dashboard_image(image, "s3://test/dash.jpg", yolo_model=mock_yolo)
        
        print(f"Result Status: {result.get('status')}")
        assert result.get("status") == "CRITICAL"
        assert result["data"].get("safety_net_triggered") is True
        print("✅ Dashboard MISS Fallback Passed")

async def verify_exterior_gate4_fallback():
    print("\n--- [Test 3] Exterior Gate 4 (Low Conf) Fallback & AL ---")
    from ai.app.services.visual.domains.exterior_service import analyze_exterior_image
    
    mock_yolo = MagicMock()
    # Mock return box with low confidence (0.4)
    box = MagicMock()
    box.cls = [0]
    box.conf = [0.4]
    box.xywh = [[100, 100, 50, 50]]
    mock_yolo.names = {0: "doorouter_dent"}
    mock_yolo.predict.return_value = [MagicMock(boxes=[box])]
    
    mock_llm_general = AsyncMock(return_value=VisualResponse(status="CRITICAL", analysis_type="LLM", category="EXTERIOR", data={}))
    mock_al_trigger = AsyncMock()
    
    with patch('ai.app.services.visual.domains.exterior_service.analyze_general_image', mock_llm_general), \
         patch('ai.app.services.visual.domains.exterior_service._trigger_al_collection', mock_al_trigger):
        
        image = MagicMock()
        image.width, image.height = 1000, 1000
        result = await analyze_exterior_image(image, "s3://test/ext.jpg", exterior_model=mock_yolo)
        
        print(f"Gate: {result['data']['decision_info']['gate']}")
        assert result['data']['decision_info']['gate'] == 4
        mock_al_trigger.assert_called_once()
        print("✅ Exterior Gate 4 Fallback & AL Trigger Passed")

async def main():
    try:
        await verify_router_fallback()
        await verify_dashboard_miss_fallback()
        await verify_exterior_gate4_fallback()
        print("\n✨ ALL CRITICAL FALLBACK SCENARIOS VERIFIED!")
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
