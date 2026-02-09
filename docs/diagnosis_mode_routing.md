# 진단 결과 경로 (결과창 vs 대화창)

## 결론

- **사진/소리/데이터 진단 모두 동일한 경로**를 탄다.  
  **통합 진단 API(comprehensive)** 가 내려주는 `response_mode`(REPORT / INTERACTIVE)에 따라  
  백엔드가 세션 상태를 정하고, 프론트는 그에 따라 **결과창** 또는 **대화창(INTERACTIVE)** 으로 분기한다.
- **데이터 진단만** 결과창으로만 가는 별도 분기는 **백엔드/프론트에 없다**.  
  데이터 진단이 항상 결과창으로만 간다면, **통합 진단 API가 데이터만 있을 때 REPORT를 반환**하고 있기 때문이다.

---

## 1. 공통 흐름 (사진/소리/데이터 동일)

1. **백엔드**  
   - `processInitialPhase`에서 시각/청각/이상감지(anomaly) 결과를 모아  
     **통합 진단 API** `callComprehensiveDiagnosis(aiRequest)` 한 번 호출.
2. **통합 진단 API 응답**  
   - `response_mode`: `"REPORT"` 또는 `"INTERACTIVE"`.
3. **백엔드**  
   - `saveDiagnosisResult()`에서 **response_mode만** 보고 분기:
     - `REPORT` → `DiagStatus.DONE`, 결과 저장 → 폴링 시 `status: DONE`, `responseMode: REPORT`
     - 그 외(INTERACTIVE) → `DiagStatus.ACTION_REQUIRED`, interactive_data 저장 → 폴링 시 `status: ACTION_REQUIRED`, `responseMode: INTERACTIVE`
   - **triggerType(DATA/VISUAL/AUDIO)** 에 따른 분기는 없음.
4. **프론트 (AiProfessionalDiag)**  
   - `getDiagnosisSessionStatus(sessionId)` 폴링 결과의 `status` / `responseMode`만 보고:
     - `INTERACTIVE` 또는 `ACTION_REQUIRED` → **대화창** (mode = INTERACTIVE)
     - `REPORT` 또는 `DONE` 등 → **결과창** (mode = REPORT)  
   - **어떤 진단 타입(데이터/사진/소리)으로 시작했는지는 보지 않음.**

→ 따라서 **“mode에 따라 경로가 갈린다”** = **통합 진단 API가 내려준 response_mode에 따라** 결과창/대화창이 갈린다.

---

## 2. 데이터 진단이 “무조건 결과창”으로 보일 수 있는 이유

- **백엔드**  
  - `saveDiagnosisResult()`에서  
    `response_mode`가 없으면 **기본값 "REPORT"** 사용:  
    `response.getOrDefault("response_mode", "REPORT")`.  
  - 따라서 API가 `response_mode`를 안 주거나, 예외/파싱 문제로 못 읽으면 **항상 REPORT → 결과창**으로 간다.
- **통합 진단 API(실서비스)**  
  - “데이터만 있고 사진/소리는 없다”는 요청에 대해,  
    바로 리포트를 내려주도록 설계되어 **항상 REPORT**를 줄 수 있다.  
  - 그렇게 되어 있으면 데이터 진단은 **항상 결과창**으로만 가게 된다.

---

## 3. connect comprehensive Mock 기준 (참고)

- Mock 로직:  
  - `has_media = (visual 있음) or (audio 있음)`  
  - **`has_media and user_reply_count >= 3`** → REPORT  
  - **그 외**(데이터만 있거나, 0회차 등) → **INTERACTIVE** (대화 시나리오 메시지 반환)
- 따라서 **데이터만 보내는 진단**이면 `has_media = false` → Mock은 **INTERACTIVE**를 반환하고,  
  이 경우 **대화창**으로 가는 것이 정상이다.  
  (실제로 결과창으로만 간다면, Mock이 아니라 다른 comprehensive API를 쓰고 있거나, 기본값 REPORT가 적용되고 있을 가능성이 큼.)

---

## 4. 데이터 진단도 mode에 따라 결과창/대화창이 갈리게 하려면

- **백엔드/프론트는 수정할 필요 없음.**  
  이미 **response_mode 한 값**으로만 결과창/대화창이 결정된다.
- **통합 진단 API(comprehensive)** 쪽에서:
  - “데이터만 있는 요청”에 대해서도  
    - 추가 정보가 필요하면 → **INTERACTIVE** 반환  
    - 충분하면 → **REPORT** 반환  
  - 이렇게만 바꿔주면, 데이터 진단도 사진/소리와 같이 **mode에 따라** 결과창 또는 대화창으로 간다.

---

## 5. 참고 코드 위치

| 구분 | 파일 | 내용 |
|------|------|------|
| 통합 진단 호출 | `AiDiagnosisService.processInitialPhase` | visual/audio/anomaly 합쳐서 `callComprehensiveDiagnosis` 1회 호출 |
| response_mode로 저장 분기 | `AiDiagnosisService.saveDiagnosisResult` | `response_mode` → DONE vs ACTION_REQUIRED, **기본값 "REPORT"** |
| 세션 상태/결과 조회 | `AiDiagnosisService.getDiagnosisResult` | DB에 저장된 `responseMode`/status 그대로 반환 |
| 프론트 분기 | `AiProfessionalDiag.tsx` (폴링) | `currentStatus` / `responseMode`만 보고 INTERACTIVE vs REPORT 화면 전환 |
