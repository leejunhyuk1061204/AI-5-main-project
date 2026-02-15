# 테스트 체크리스트 — seed 파일 및 소모품 수정 (8ae179e)

**커밋**: `8ae179e9f8655b1792f46c01e0661b6d9f450985`  
**변경 요약**: DTC/차량/소모품 시드 수정, 차계부·OCR 수량(quantity) 추가, 소모품 코드 리팩터링(TIRE_* / BRAKE_PAD_*)

---

## 1. 반드시 할 테스트 (필수)

### 1.1 백엔드 단위/통합 테스트
| 항목 | 명령 | 비고 |
|------|------|------|
| WearFactorService 단위 테스트 | `./gradlew :backend:test --tests "kr.co.himedia.service.WearFactorServiceTest"` | 소모품 코드 `TIRE_FL` 등, `BRAKE_PAD_FRONT/REAR` 반영 여부 |
| WearFactor 통합 테스트 | `./gradlew :backend:test --tests "kr.co.himedia.service.WearFactorIntegrationTest"` | `createAllConsumables()`가 새 시드 코드와 일치하는지 |

### 1.2 DB·시드
| 항목 | 확인 내용 |
|------|-----------|
| 스키마 적용 | `db/schema.sql`에 `maintenance_history`(또는 정비 이력 테이블)에 `quantity` 컬럼 존재 여부 |
| 시드 로드 | `seed_consumable.sql` → consumable_items 15개 (ENGINE_OIL, TIRE_FL/FR/RL/RR, BRAKE_PAD_FRONT/REAR, BATTERY_12V, COOLANT, AIR_FILTER 등) |
| 차량/DTC 시드 | `seed_car_models*.sql`, `seed_dtc_data*.sql` 로드 후 차량 모델·DTC 조회 정상 |

### 1.3 차계부·정비 이력 (수량)
| 시나리오 | 확인 내용 |
|----------|-----------|
| 정비 이력 등록 (수동) | `quantity` 없음 → 기본 1로 저장되는지 |
| 정비 이력 등록 (수동) | `quantity=2` 등 지정 시 저장·조회 시 2로 나오는지 |
| 정비 이력 수정 | 기존 이력 수정 시 `quantity` 변경 반영되는지 |
| API 응답 | `MaintenanceHistoryResponse`에 `quantity` 필드 포함·null 시 1로 내려가는지 |

### 1.4 OCR·영수증 분석
| 시나리오 | 확인 내용 |
|----------|-----------|
| OCR 분석 결과 | 영수증에 "2개", "타이어 2개" 등 있을 때 `OcrAnalysisResponse.quantity` 값 반환 |
| OCR 후 저장 | 분석 결과의 quantity가 정비 이력에 반영 (null이면 1) |
| 수동 데이터(manualData) | JSON에 `quantity` 넣어서 요청 시 백엔드에서 반영되는지 (프론트는 현재 manualData에 quantity 미포함 가능성 있음 → 필요 시 프론트에 수량 입력·전달 추가 후 확인) |

### 1.5 소모품 코드 리팩터링
| 구분 | 확인 내용 |
|------|-----------|
| 마모 계수 계산 | 주행 종료 후 `WearFactorService.calculateWearFactorsLocal` 호출 시 `TIRE_FL` 등 4개, `BRAKE_PAD_FRONT`/`BRAKE_PAD_REAR` 각각 계산·저장 |
| ConsumableConstants | `getReplacementCycle("TIRE_FL")`, `getReplacementCycle("BRAKE_PAD_FRONT")` 등 호출 시 예외 없이 주기 반환 |
| 알 수 없는 코드 | 시드에 없는 소모품 코드 들어오면 스킵 또는 예외 처리 동작 확인 |

### 1.6 AI 진단·DTC
| 항목 | 확인 내용 |
|------|-----------|
| DTC 관련 소모품 | `CABIN_FILTER` 제거됨 → DTC 진단 시 엔진/배기 관련 소모품에 CABIN_FILTER 미포함 |
| 소모품 필터 | 주의 필요(80% 이하) + DTC 시 엔진/배기 관련 + ENGINE_OIL, BRAKE_PAD_FRONT/REAR, BATTERY_12V 항상 포함 |

### 1.7 프론트엔드 — 정비/영수증
| 화면 | 확인 내용 |
|------|-----------|
| ReceiptResult (영수증 결과) | 소모품 목록이 시드와 동일 (타이어 위치 선택, 브레이크 앞/뒤 등) |
| ReceiptResult | "타이어(위치 선택)" / "브레이크 패드(위치 선택)" 선택 시 위치 모달 표시, 복수 선택 후 저장 시 해당 코드별 이력 생성 |
| ReceiptResult | OCR 결과에 수량이 있으면 모달에 "영수증에 수량 N개로 인식됨" 표시 |
| AllHistoryList | 정비 이력 리스트에서 `quantity > 1`일 때 "항목명 x2" 형태로 표시 |
| 주유 저장 | 기존처럼 정상 동작 (변경 없음) |

### 1.8 기타 백엔드
| 항목 | 확인 내용 |
|------|-----------|
| WearFactorService | `@Async` 제거 → 주행 종료 후 마모 계수 계산이 **동기**로 완료되는지 (트립 종료 API 응답 타이밍에 반영) |
| MAF 기본값 | 차량 모델별 MAF 제거·default 18.0 → 에어필터 마모 계산 시 기본값 18.0 사용 |
| getConfidence 제거 | `ConsumableConstants.getConfidence()` 호출부가 코드에서 제거되었는지 (호출 시 컴파일 에러 확인) |

---

## 2. 선택 테스트 (가능하면 수행)

| 항목 | 내용 |
|------|------|
| 주행 플로우 E2E | `tests/flow/test_driving.py` — 토큰/차량 ID 갱신 후 10분 주행, 평균 80~90 km/h 구간으로 마모 계수·급가속 감점 구간 동작 확인 |
| Docker 기동 | `docker-compose.yml` 변경분 반영 후 DB·앱 컨테이너 기동, 시드 로드 스크립트(`seed_*_load.docker.sql` 등) 정상 실행 |
| 기존 정비 이력 | DB에 `quantity` 컬럼 추가 마이그레이션 시 기존 행은 DEFAULT 1 적용되는지 (또는 nullable이면 null 처리 일관성) |

---

## 3. 요약 — 우선순위

1. **백엔드 테스트**: `WearFactorServiceTest`, `WearFactorIntegrationTest` 실행  
2. **DB·시드**: schema + seed_consumable + (필요 시) 차량/DTC 시드 로드  
3. **차계부 수량**: 정비 이력 등록/수정/조회 API에서 `quantity` 동작  
4. **OCR**: 영수증 분석 → quantity 파싱 → 저장 플로우  
5. **프론트**: ReceiptResult 소모품·위치 선택·수량 문구, AllHistoryList 수량 표시  
6. **주행·마모**: 주행 종료 후 동기 마모 계수 계산 및 TIRE_* / BRAKE_PAD_* 반영  

---

**참고**: `ConsumableConstants.getConfidence()` 제거로 인해 다른 모듈에서 해당 메서드를 호출하고 있다면 컴파일/런타임 오류가 날 수 있으므로, 프로젝트 전체에서 `getConfidence` 검색 후 제거·대체 여부를 확인하는 것이 좋습니다.
