---
description: RAG 데이터 수집 및 자동화 설정 (Turbo Mode)
---

// turbo-all

# RAG Data Setup Workflow

이 워크플로우는 사용자 정의 '헌법'을 준수하며 RAG 데이터를 자동으로 수집합니다.

## Steps

1. **디렉토리 생성**
   - 수집된 데이터를 저장할 `data/dtc`, `data/manuals` 폴더 생성.

2. **DTC 요약 크롤링 (Dry-Run)**
   - `python scripts/scrape_dtc.py --limit 1` 실행 후 결과 보고.

3. **Charm.li 스크래핑 (Dry-Run)**
   - `python scripts/scrape_charmli.py --limit 1` 실행 후 결과 보고.

4. **사용자 승인 후 전체 작업 진행**
   - 승인 시 `--full` 옵션으로 전체 수집 수행.
