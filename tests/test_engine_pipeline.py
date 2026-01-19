# tests/test_engine_pipeline.py
import pytest
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from PIL import Image
import io

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.app.services.engine_anomaly_service import EngineAnomalyPipeline, EngineAnomalyResult
from ai.app.schemas.visual_schema import DetectionResult, DetectionItem

@pytest.mark.asyncio
async def test_pipeline_path_b_fallback():
    """Test Path B: No detections -> General LLM Analysis"""
    
    # Mock Services
    with patch('ai.app.services.engine_anomaly_service.run_yolo_inference', new_callable=AsyncMock) as mock_yolo, \
         patch('ai.app.services.engine_anomaly_service.analyze_general_image', new_callable=AsyncMock) as mock_llm, \
         patch('ai.app.services.engine_anomaly_service.EngineAnomalyPipeline._download_image_secure') as mock_download:
         
        # Setup Mocks
        mock_download.return_value = b"fake_image_bytes"
        
        # YOLO returns 0 detections
        mock_yolo.return_value = DetectionResult(
            detections=[],
            detected_count=0,
            image_url="http://mock.s3/img.jpg",
            elapsed_time=0.1
        )
        
        # LLM returns valid response
        mock_llm_response = MagicMock()
        mock_llm_response.category = "ENGINE"
        mock_llm_response.dict.return_value = {"type": "VEHICLE", "sub_type": "ENGINE"}
        mock_llm.return_value = mock_llm_response
        
        # Initialize Pipeline
        pipeline = EngineAnomalyPipeline()
        pipeline.s3_client = MagicMock() # Mock S3
        
        # Run
        result = await pipeline.analyze("http://mock.s3/img.jpg")
        
        # Assertions
        assert result["status"] == "SUCCESS"
        assert result["path"] == "B"
        mock_llm.assert_called_once()
        # Check Hard Negative Mining (Since category=ENGINE)
        pipeline.s3_client.put_object.assert_called() 

@pytest.mark.asyncio
async def test_pipeline_path_a_ev_classification():
    """Test Path A: Detections -> EV Classification -> Anomaly"""
    
    with patch('ai.app.services.engine_anomaly_service.run_yolo_inference', new_callable=AsyncMock) as mock_yolo, \
         patch('ai.app.services.engine_anomaly_service.crop_detected_parts', new_callable=AsyncMock) as mock_crop, \
         patch('ai.app.services.engine_anomaly_service.EngineAnomalyPipeline._download_image_secure') as mock_download, \
         patch('ai.app.services.engine_anomaly_service.EngineAnomalyPipeline._process_single_part', new_callable=AsyncMock) as mock_process:
         
        # Setup Mocks
        mock_download.return_value = b"fake_image_bytes"
        
        # YOLO returns EV Parts (Inverter)
        mock_yolo.return_value = DetectionResult(
            detections=[
                DetectionItem(label="Inverter", confidence=0.9, bbox=[100,100,50,50]),
                DetectionItem(label="Battery", confidence=0.8, bbox=[200,200,50,50])
            ],
            detected_count=2,
            image_url="http://mock.s3/img.jpg",
            elapsed_time=0.1
        )
        
        mock_crop.return_value = {"Inverter": (MagicMock(), [100,100,50,50]), "Battery": (MagicMock(), [200,200,50,50])}
        
        # Mock Part Processing Result
        mock_process.return_value = EngineAnomalyResult(
            part_name="Inverter", is_anomaly=True, anomaly_score=0.8, threshold=0.7,
            defect_label="Test", defect_category="TEST", description="test", severity="WARNING", recommended_action="Action",
            crop_url="url", heatmap_url="url"
        )
        
        # Initialize Pipeline
        pipeline = EngineAnomalyPipeline()
        pipeline.s3_client = MagicMock()
        
        # Run
        result = await pipeline.analyze("http://mock.s3/img.jpg")
        
        # Assertions
        assert result["status"] == "SUCCESS"
        assert result["path"] == "A"
        assert result["vehicle_type"] == "EV" # Inverter exists
        assert "Inverter" in result["results"]

if __name__ == "__main__":
    # If using 'python tests/test_engine_pipeline.py'
    asyncio.run(test_pipeline_path_b_fallback())
    asyncio.run(test_pipeline_path_a_ev_classification())
    print("All tests passed!")
