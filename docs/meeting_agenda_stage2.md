# 진단/채팅 기능 고도화 회의 안건 (2단계)

1단계(파일 선택 기능) 완료 후, 시스템의 안정성과 사용자 경험을 향상시키기 위한 차세대 구현 단계에 대한 회의 안건입니다.

---

## 1. 백엔드 인프라 활용: 기존 RabbitMQ 기반 비동기 전환
이미 구축된 RabbitMQ 인프라를 활용하여 `replyToSession`(채팅 답변) 프로세스를 비동기 및 재시도 가능한 구조로 개편합니다.

- **연동 방안**: 
    - `ai.diagnosis.queue` 및 이미 설정된 DLX/DLQ를 활용하여 시스템 일관성 유지.
    - 분석 실패 시 가용 가능한 재시도 로직 적용.
    - **Context**: 3~10초 소요되는 AI 서버 응답 대기 시간을 비동기로 전환하여 클라이언트 타임아웃 방지 (`processUnifiedFlow` 및 `replyToSession` 모두 적용).
- **회의 포인트**: 
    - RabbitMQ 메세지 구조 설계 및 `Processing` 상태 관리 전략 (`REPLY_PROCESSING` 등 신규 상태 추가 여부).
    - 분석 완료 시 클라이언트로의 알림 방식 (Polling vs WebSocket/Push).

## 2. 데이터 통합 및 이력 관리 (Aggregator)
AI 서버로 전달할 데이터의 구성과 정합성을 보장하기 위한 상세 설계입니다.

- **이전 대화 이력 및 미디어 관리**: 
    - **DB 저장 방식**: `DIAG_RESULT` 테이블의 `interactive_json` 컬럼에 전체 대화 내역(`conversation`)을 축적.
    - **미디어 분석 결과 연동 (Key Update)**: 
        - 사용자 사진/음성 -> S3 저장 -> **AI 서버 분석(YOLO/AST)** -> **`ai_evidences` 테이블의 `ai_analysis`(JSONB) 업데이트**.
        - 최종 GPT 요청 시 `ai_evidences`에 저장된 분석 결과(JSON)를 텍스트로 변환하여 컨텍스트에 포함. (GPT가 직접 이미지를 보는 대신 분석된 '데이터'를 기반으로 판단)
    - **데이터 정합성**: 대화 중 추가된 모든 미디어(사진, 녹음파일)는 `diag_session_id`로 연결되어 차후 리포트 생성 시 근거 데이터로 활용.
- **AI 서버 전달 핵심 데이터 (Incremental Phase)**:
    - **Phase 1: 초기 진단 (6대 항목)**: `vehicleInfo`, `consumablesStatus`, `visual`, `audio`, `anomaly`, `knowledge` (대화 이력 없음)
    - **Phase 2: 채팅 답변 (7대 항목)**: 위 6대 항목 + `conversation_history` (누적된 대화 및 미디어 분석 결과 포함)

- **데이터 전송 방식 및 `interactive_json` 규격**:
    - **Payload 구조**: `vehicleId`와 `tripId` 대신 조회된 실제 데이터(7대 요소)를 전송.
    - **`interactive_json` 상세 스펙**:
        ```json
        {
          "message": "AI의 다음 질문/응답",
          "conversation": [
            {
              "role": "user", 
              "content": "공회전 시 소음이 커요", 
              "media_refs": [
                { "type": "AUDIO", "evidence_id": "UUID", "analysis": "엔진 벨트 슬립 소음 90% 일치" }
              ]
            }
          ],
          "requested_actions": ["IMAGE", "AUDIO"]
        }
        ```
    - **동기/비동기 정렬**: `processUnifiedFlow`(비동기)와 `replyToSession`(동기)이 동일한 `AiUnifiedRequestDto` 규격을 사용하도록 통일.

## 3. 채팅 UI 및 사용자 경험 개선
AI의 요구사항에 따라 실시간으로 변화하는 인터페이스를 구현합니다.

- **동적 액션 버튼**: AI 응답 메시지 내 `requested_actions` 항목에 따른 버튼 노출 ('사진 촬영', '소리 녹음').
- **자동 복귀 로직**: 촬영/녹음 완료 시 현재 대화 중인 채팅창으로 즉시 복귀 및 자동 업로드 연동.
- **분석 피드백**: "AI 분석 중..." 애니메이션 메시지 및 폴링 중 시각적 효과 (`replyToSession` 완료 대기 시에도 동일 UI 적용).

---

## 다음 회의 시 결정할 사항
1. RabbitMQ 메시지 구조 및 `Processing` 상태 관리 전략 확정.
2. AI 서버 전용 통합 JSON 규격(7대 데이터) 확정.
3. 채팅창 동적 버튼의 우선순위 및 UI 디자인 확정.
