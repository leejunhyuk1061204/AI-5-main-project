# RunPod 자동 번역 가이드

이 폴더(`runpod`)는 RunPod 인스턴스에서 DTC 데이터를 쉽게 번역하기 위해 구성된 독립 패키지입니다.

## 📁 폴더 구조
```text
runpod/
├── data/                  # 번역할 데이터 파일이 들어있는 폴더
│   ├── github_dtc_bulk.json
│   ├── batch_dtc_summary.json
│   └── github_dtc_codes.db
├── scripts/               # 스크립트는 루트에 있습니다.
├── translate_dtc_runpod.py # 메인 번역 실행 스크립트
├── automotive_terms.py     # 자동차 용어 사전 (번역 품질 향상용)
└── run_translation.sh      # ✅ 원클릭 실행 스크립트
```

## 🚀 실행 방법 (매우 간단)

RunPod 터미널에서 `runpod` 폴더로 이동한 후, 아래 명령어를 입력하세요.

```bash
# 실행 권한 부여 (최초 1회)
chmod +x run_translation.sh

# 번역 시작
./run_translation.sh
```

이 스크립트는 다음 작업을 자동으로 수행합니다:
1. **Ollama 설치**: 이미 설치되어 있으면 건너뜁니다.
2. **서버 실행**: Ollama 서버를 백그라운드에서 켭니다.
3. **모델 다운로드**: 고성능 번역을 위한 `qwen2.5:32b` 모델을 받습니다 (약 20GB).
4. **번역 실행**: 데이터 파일들을 찾아 번역을 시작합니다.
5. **결과 저장**: `runpod/data/translated_dtc_final.json` 파일에 저장됩니다.

## 💾 결과물 가져오기
번역이 완료되면 `runpod/data/translated_dtc_final.json` 파일을 다운로드하여 사용하세요.

## ⚠️ 주의사항
- **GPU 메모리**: 최소 24GB VRAM 이상의 인스턴스(RTX 3090, 4090 등)를 권장합니다.
- **이어하기**: 중간에 멈췄거나 오류가 나도, 다시 실행하면 `translated_cache.json`을 통해 이어서 진행합니다.
