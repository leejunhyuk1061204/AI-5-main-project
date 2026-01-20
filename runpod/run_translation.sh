#!/bin/bash

echo "========================================"
echo "   RunPod DTC Translation Systems Setup   "
echo "========================================"

# 1. Ollama 설치 확인 및 설치
if ! command -v ollama &> /dev/null
then
    echo "Creating install script..."
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "✅ Ollama is already installed."
fi

# 2. Ollama 서버 백그라운드 실행
echo "Starting Ollama server..."
nohup ollama serve > ollama.log 2>&1 &
# 서버가 뜰 때까지 잠시 대기
sleep 5

# 3. 모델 다운로드
echo "Pulling Qwen2.5-32B Model..."
ollama pull qwen2.5:32b

# 4. 파이썬 의존성 설치
echo "Installing Python dependencies..."
pip install aiohttp tqdm

# 5. 번역 스크립트 실행
echo "Starting Translation Script..."
python translate_dtc_runpod.py

echo "========================================"
echo "   All Tasks Completed!   "
echo "   Check 'data/translated_dtc_final.json'   "
echo "========================================"
