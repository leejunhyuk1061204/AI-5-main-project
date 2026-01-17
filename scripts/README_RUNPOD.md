## 1. 사전 준비 (RunPod 인스턴스)

RunPod에서 **RTX 3090 (24GB VRAM)** 이상의 GPU 인스턴스를 생성하세요.
(템플릿: `Ollama` 또는 `PyTorch` 최신 버전 추천)

### ⚠️ 필수 전달 파일 확인
실행 전 다음 파일들이 같은 폴더에 있는지 확인하세요:
- `translate_dtc_runpod.py` (메인 스크립트)
- `automotive_terms.py` (자동차 용어 사전)
- `data/dtc/` (번역할 DTC 데이터 폴더)

## 2. Ollama 및 모델 설정

터미널에 접속하여 아래 명령어를 순서대로 실행합니다.

```bash
# 1. Ollama 설치 (Ollama 템플릿이 아닌 경우에만 실행)
curl -fsSL https://ollama.com/install.sh | sh

# 2. Ollama 서버 백그라운드 실행
ollama serve > ollama.log 2>&1 &

# 3. Qwen2.5-32B 모델 내려받기 (약 18~20GB)
ollama pull qwen2.5:32b
```

## 3. 번역 스크립트 실행 환경 구축

필요한 라이브러리를 설치합니다.

```bash
pip install aiohttp tqdm
```

## 4. 번역 시작

프로젝트의 `scripts/` 폴더에서 아래 명령어를 실행합니다.
데이터는 `data/dtc/` 폴더 내의 파일들을 자동으로 탐색하여 통합 번역합니다.

```bash
python translate_dtc_runpod.py
```

## 5. 결과 확인 및 중단점 지원

- **결과물**: `data/dtc/translated_dtc_final.json` 파일에 모든 번역 데이터가 저장됩니다.
- **이어하기**: 작업 도중 멈추더라도 `data/dtc/translated_cache.json` 파일이 있으면, 진행했던 부분은 건너뛰고 나머지부터 다시 시작합니다.

## 주의사항
- **비동기 처리**: 현재 스크립트는 `BATCH_SIZE=5`로 설정되어 있습니다. GPU 부하가 너무 크면 스크립트 상단의 숫자를 줄여주세요.
- **메모리**: Qwen2.5:32b 모델은 실행 시 약 18~22GB의 VRAM을 사용합니다.
