#!/bin/bash

# ==========================================
# RunPod Start Script for Car-Sentry AI
# ==========================================

echo "🚀 [Start] Car-Sentry AI 환경 설정을 시작합니다..."

# 1. 시스템 패키지 설치 (오디오/비디오 처리에 필요)
echo "📦 [System] 필수 시스템 패키지 설치 중 (libsndfile1, ffmpeg)..."
apt-get update && apt-get install -y libsndfile1 ffmpeg

# 2. 실행 권한 부여
echo "🔑 [Permission] 스크립트 실행 권한 부여 중..."
chmod +x scripts/vision/*.py
chmod +x scripts/audio/*.py

# 3. YOLO 경로 자동 수정 (런팟 대용량 스토리지 대응)
LARGE_DATA="/workspace/large_data"
if [ -d "$LARGE_DATA" ]; then
  echo "📂 [Path-Fix] $LARGE_DATA 가 감지되어 YOLO data.yaml 경로를 자동 수정합니다..."
  # data.yaml 파일 내의 'path:' 설정을 런팟 경로로 변경
  find "$LARGE_DATA" -name "data.yaml" -exec sed -i "s|^path:.*|path: $LARGE_DATA/yolo|g" {} +
fi

# 4. Python 패키지 설치

# 3. 서버 실행
echo "✅ [Ready] FastAPI 서버를 시작합니다 (Port: 8000)..."
# 0.0.0.0으로 열어야 외부에서 접속 가능
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
