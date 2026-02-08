# 블루투스/OBD 관련 수정 사항 정리

로그 기준: `obd_test_log_2026-02-08T10-07-00-304Z.txt`  
분석 일자: 2026-02-08

---

## 1. 수정 대상 요약

| 우선순위 | 항목 | 담당 파일 | 내용 |
|----------|------|-----------|------|
| P0 | BackgroundService start/stop 반복 | App.tsx, ObdService.ts | 권한 다이얼로그·포커스 변화 시 서비스가 반복 기동/중지됨 |
| P0 | active 시 무조건 stop | App.tsx | 포그라운드 복귀 시 무조건 서비스 중지 → 디바운스 또는 조건부 처리 필요 |
| P1 | PID 응답 타임아웃 10초 초과 | ObdService.ts | 50ms×200 루프가 실제로 13~52초 걸림 → 단일 타이머로 고정 |
| P2 | AppState 리스너 중복/역할 혼선 | ObdService.ts, App.tsx | 백그라운드 정책을 한 곳으로 통합 |

---

## 2. 상세 수정 사항

### 2.1 [P0] App.tsx — active 시 무조건 stop 제거 및 디바운스

**현상**  
- `nextAppState === 'active'`일 때마다 `BackgroundService.stop()` 호출  
- 알림 권한 다이얼로그가 뜨면 잠깐 `background` → 다이얼로그 닫으면 `active` → 즉시 stop  
- 사용자가 앱을 실제로 나간 게 아닌데도 서비스가 반복 기동/중지됨

**수정 방향**

1. **active 시 즉시 stop 제거**  
   - `active` 수신 시 곧바로 `BackgroundService.stop()` 호출하지 않기.

2. **디바운스 도입**  
   - `active` 수신 시 "포그라운드 복귀"로 간주하고, **N초(예: 2~3초) 동안 다시 `background`로 가지 않을 때만** stop 실행.  
   - N초 이내에 다시 `background`로 가면 타이머 취소하고 stop 하지 않음.

3. **선택: 권한 요청 중 플래그**  
   - ObdService에서 `PermissionsAndroid.request(POST_NOTIFICATIONS)` 호출 전후에 플래그 설정 가능.  
   - App.tsx에서 해당 플래그가 설정된 동안에는 `active` → stop 하지 않도록 할 수 있음 (구현 시 ObdService와 약속 필요).

**수정 파일**  
- `frontend/App.tsx`  
  - AppState `change` 리스너 내부 `nextAppState === 'active'` 분기  
  - 디바운스 타이머 변수(Ref 등) 및 로직 추가

**검증**  
- Elm327 테스트 화면에서 OBD 연결 → 폴링 시작 → 알림 권한 요청 시, 로그에 BackgroundService가 1~2초 만에 Stopping/Stopped가 반복되지 않는지 확인.

---

### 2.2 [P0] ObdService.ts — 알림 권한 요청 시점과 BackgroundService 기동 분리

**현상**  
- `startPolling()` 내부에서 (1) 알림 권한 요청 (2) 권한 있으면 `BackgroundService.start()` 호출.  
- 권한 요청 다이얼로그가 뜨는 순간 AppState가 `background`로 바뀌고, App.tsx가 이미 `BackgroundService.start()`를 호출함.  
- 다이얼로그가 닫히면 `active` → App.tsx가 `BackgroundService.stop()` 호출 → 우리가 의도한 “폴링 중 백그라운드 유지”와 어긋남.

**수정 방향**

1. **권한 요청을 폴링 시작 전으로 이동**  
   - OBD 연결/폴링 시작 **전**에 알림 권한이 없으면 먼저 요청.  
   - 또는 앱 최초 실행/설정 화면에서 미리 요청하고, `startPolling()`에서는 권한만 체크하고 없으면 폴링만 중단.

2. **startPolling() 내부에서는 권한 있을 때만 BackgroundService.start()**  
   - 현재도 권한 없으면 `Alert` 후 `return`하지만, **권한 요청 다이얼로그가 뜨는 시점**을 `startPolling()` 밖으로 빼면, “폴링 시작 직후 다이얼로그 → background → active” 연쇄를 줄일 수 있음.

**수정 파일**  
- `frontend/services/ObdService.ts`  
  - `startPolling()` 내부 Android 13+ 알림 권한 체크/요청 위치 검토  
  - 필요 시 권한 요청은 호출 측(예: ObdConnect, Elm327TestScreen) 또는 앱 초기화로 이동

**검증**  
- 알림 권한이 이미 허용된 상태에서 폴링 시작 시 BackgroundService가 한 번만 start 되는지 로그로 확인.

---

### 2.3 [P1] ObdService.ts — BLE PID 응답 타임아웃을 단일 타이머로 고정

**현상**  
- BLE 응답 대기가 `maxWaitMs = 10000`인데, 로그에는 13684ms, 14771ms, 52496ms 등 10초를 넘는 타임아웃이 찍힘.  
- 원인: `while (this.currentPid !== null && waited < maxWaitMs)` + `await this.delay(stepMs)` 50ms×200회 루프.  
- JS 스레드가 바쁘면 한 루프가 10초보다 훨씬 길어져서, “의도한 10초”가 아닌 실제 경과 시간만큼 대기함.

**수정 방향**

1. **10초를 “한 번의 타이머”로 보장**  
   - `Promise.race([ 응답 대기, delay(10000) ])` 형태로 변경.  
   - 10초가 지나면 무조건 타임아웃 처리하고, 루프는 “응답 도착 여부” 체크용으로만 사용하거나 제거.

2. **타임아웃 시 로그/처리**  
   - 기존과 동일하게 `response timeout` 로그, `incrementPidFailCount`, `currentPid = null` 등 유지.  
   - 단, `elapsed`는 “실제 10초”를 넘지 않도록 타이머 기반으로 계산.

**수정 파일**  
- `frontend/services/ObdService.ts`  
  - `pollingLoop` 내 BLE 분기: `while` 대기 루프 제거 후 `Promise.race` + 단일 `setTimeout(10000)` (또는 `delay(10000)`) 적용

**검증**  
- 미지원 PID에 대해 타임아웃 로그가 약 10000ms 전후로만 찍히는지, 50초 등으로 늘어나지 않는지 확인.

---

### 2.4 [P2] AppState 리스너 역할 통합

**현상**  
- ObdService: `AppState`에서 `background`일 때 로그만 남기고, 실제로는 `BackgroundService.start()`를 호출하지 않음.  
- App.tsx: `background`일 때 `ObdService.isConnected()`면 start, `active`일 때 무조건 stop.  
- “언제 start/stop 할지” 정책이 App.tsx에만 있고, ObdService의 리스너는 혼란만 가중.

**수정 방향**

1. **백그라운드 서비스 start/stop 정책을 App.tsx 한 곳으로 통일**  
   - App.tsx: `background` → (조건 만족 시) start, `active` → 디바운스 후 stop (2.1 반영).

2. **ObdService의 AppState 리스너 제거 또는 축소**  
   - “App went to background, ensuring...” 로그만 남기는 리스너는 제거하거나,  
   - “디바운스 후 start 요청” 등 App.tsx와 역할이 겹치지 않는 보조 역할만 부여.

**수정 파일**  
- `frontend/services/ObdService.ts`  
  - 생성자(또는 초기화) 내 `AppState.addEventListener('change', ...)` 제거 또는 역할 축소  
- `frontend/App.tsx`  
  - 위 2.1 반영으로 여기서만 start/stop 제어

**검증**  
- 앱을 백그라운드로 보냈다가 다시 포그라운드로 올렸을 때, 서비스가 한 번만 start되고 디바운스 후 한 번만 stop되는지 로그로 확인.

---

## 3. 선택 사항 (우선순위 낮음)

- **미지원 PID 빠른 비활성화**  
  - 타임아웃/NO DATA가 나온 PID는 재시도 횟수 제한을 두고, 일정 횟수 초과 시 해당 PID를 큐에서 제외하거나 우선순위를 낮춤.  
  - 이미 PidFailIgnore 등이 있으면, 비활성화 조건/타이밍만 조정하면 됨.

- **ObdConnect / 테스트 화면에서 권한 선요청**  
  - OBD 연결 버튼을 누르기 전에 알림 권한이 없으면 먼저 요청해 두면, 폴링 시작 시점에 다이얼로그가 뜨지 않아 AppState 오인을 줄일 수 있음.

---

## 4. 수정 후 체크리스트

- [ ] Elm327 테스트: OBD 연결 → 폴링 시작 후 로그에 BackgroundService Start/Stop이 1~2초 간격으로 반복되지 않음.
- [ ] 알림 권한 허용 후 폴링 시 BackgroundService가 한 번만 start됨.
- [ ] 앱을 백그라운드로 보냈다가 다시 활성화할 때, 디바운스 후 한 번만 stop됨.
- [ ] PID 타임아웃 로그가 약 10초(10000ms 전후)로만 찍힘.
- [ ] ObdService에 남아 있던 AppState 리스너가 제거되었거나 역할이 명확함.

---

## 5. 수정 후에도 남을 수 있는 리스크 (추가 검토)

P0/P1/P2 적용으로 **대부분 해결될 가능성이 높지만**, 아래 1가지는 “체감상 완전 해결”을 위해 함께 보는 것이 좋다.

### 5.1 BLE notification(수신) 구독이 실제로 살아있는지

- **리스크**: 연결은 됐는데 응답이 안 오는 경우가 “구독이 끊겼거나 중복/해제 꼬임”일 수 있음.
- **코드 확인**: ObdService는 생성자에서 `BleManagerDidUpdateValueForCharacteristic` 리스너를 **한 번만** 등록하고 해제하지 않음. PID 큐는 **한 번에 한 요청만** 처리(`currentPid` 하나, 순차 처리).  
  → 현재 구조상 “동시에 2개 요청”은 아님. 다만 앱이 백그라운드/포그라운드로 오갈 때 일부 기기·OS에서 BLE 알림이 잠시 끊기거나 지연될 수 있음.
- **정리**: 플랩핑을 줄이면 이 현상도 줄어들 가능성이 큼. 그래도 문제가 남으면 “연속 N회 응답 없음 시 `startNotification` 재호출” 같은 구독 재등록 로직을 검토할 수 있음.

---

## 6. 참고

- 로그 분석: `obd_test_log_2026-02-08T10-07-00-304Z.txt`  
- 관련 이전 논의: 권한 다이얼로그로 인한 AppState `background` 이슈, PID 타임아웃 10초 초과 원인(이벤트 루프 지연).
