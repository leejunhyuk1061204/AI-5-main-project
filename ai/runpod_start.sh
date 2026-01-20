#!/bin/bash

# ==========================================
# RunPod Start Script for Car-Sentry AI
# ==========================================

echo "🚀 [Start] Car-Sentry AI 환경 설정을 시작합니다..."

# 1. 시스템 패키지 설치 (오디오/비디오 처리에 필요)
echo "📦 [System] 필수 시스템 패키지 설치 중 (libsndfile1, ffmpeg)..."
apt-get update && apt-get install -y libsndfile1 ffmpeg

# 2. Python 패키지 설치
echo "🐍 [Python] requirements.txt 의존성 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt

# 3. 서버 실행
echo "✅ [Ready] FastAPI 서버를 시작합니다 (Port: 8000)..."
# 0.0.0.0으로 열어야 외부에서 접속 가능
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
