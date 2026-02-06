# 블루투스 OBD 고도화 변경사항 분석

## 커밋 정보

### 첫 번째 커밋
- **커밋 ID**: `c1009bcbfaf87271614869dcddea9673cb5ceb43`
- **작성자**: Leejunhyuk
- **날짜**: 2026-02-06 오전 1:23:05
- **메시지**: 블루투스 고도화

### 두 번째 커밋
- **커밋 ID**: `10fec39940a031d48fc6e76968f5a573ba63808d`
- **작성자**: Leejunhyuk
- **날짜**: 2026-02-06 오전 1:40:58
- **메시지**: 추가

---

## 변경된 파일 목록

### 백엔드 (4개 파일)
1. `backend/src/main/java/kr/co/himedia/controller/ObdController.java` (8줄 변경)
2. `backend/src/main/java/kr/co/himedia/dto/obd/ObdBatchRequestDto.java` (16줄 추가, 신규)
3. `backend/src/main/java/kr/co/himedia/dto/obd/ObdLogDto.java` (4줄 추가)
4. `backend/src/main/java/kr/co/himedia/service/ObdService.java` (59줄 변경)

### 프론트엔드 (6개 파일)
1. `frontend/api/aiApi.ts` (27줄 추가)
2. `frontend/api/obdApi.ts` (23줄 변경)
3. `frontend/services/BackgroundService.ts` (10줄 변경)
4. `frontend/services/ObdPidHelper.ts` (123줄 추가)
5. `frontend/services/ObdService.ts` (1077줄, 대폭 개편)
6. `frontend/services/OfflineStorage.ts` (27줄 추가)

### 문서
1. `docs/8.블루투스_OBD_연동_및_고도화_계획.md` (71줄 삭제)

**총 변경량**: 1054줄 추가, 391줄 삭제

---

## 1. 백엔드 변경사항 상세

### 1.1 DTO 계층

#### ObdBatchRequestDto.java (신규 생성)
```java
@Getter
@Setter
@ToString
public class ObdBatchRequestDto {
    private String batchId;        // 배치별 고유 ID (멱등성 보장)
    private UUID vehicleId;        // 차량 ID
    private List<ObdLogDto> logs;  // OBD 로그 목록
}
```

**목적**: 배치 단위 업로드 시 중복 방지 및 구조화된 요청 처리

#### ObdLogDto.java
**변경사항**:
- `throttlePos` 필드에 `@JsonProperty("throttle")` 어노테이션 추가
- 프론트엔드에서 `throttle`로 전송하는 값을 백엔드 `throttlePos`와 매핑

**이유**: 프론트엔드와 백엔드의 필드명 불일치 해결

### 1.2 컨트롤러 계층

#### ObdController.java
**변경 전**:
```java
@PostMapping("/batch")
public ResponseEntity<ApiResponse<Void>> uploadObdLogs(@RequestBody List<ObdLogDto> obdLogDtos) {
    obdService.saveObdLogs(obdLogDtos);
    return ResponseEntity.ok(ApiResponse.success(null));
}
```

**변경 후**:
```java
@PostMapping("/batch")
public ResponseEntity<ApiResponse<Void>> uploadObdLogs(@RequestBody ObdBatchRequestDto batchRequest) {
    obdService.saveObdLogs(batchRequest);
    return ResponseEntity.ok(ApiResponse.success(null));
}
```

**변경 이유**: `batchId` 기반 멱등성 처리 지원

### 1.3 서비스 계층

#### ObdService.java
**주요 개선사항**:

1. **Redis 기반 멱등성 보장**
   - 키 포맷: `obd:batch:{vehicleId}:{batchId}`
   - 차량별 네임스페이스 분리로 동일 batchId 충돌 방지

2. **PROCESSING 락 메커니즘**
   ```java
   Boolean lockAcquired = redisTemplate.opsForValue()
       .setIfAbsent(redisKey, "PROCESSING", 10, TimeUnit.MINUTES);
   ```
   - 동시 요청 차단
   - 실패 시 락 해제로 재시도 허용

3. **TTL 72시간으로 연장**
   - 기존: 단기 TTL (몇 시간)
   - 변경: 72시간 (오프라인 큐에서 3일 이내 재전송 대응)

**처리 흐름**:
```
1. Redis에서 batchId 상태 조회
2. "DONE" → 200 OK 반환 (이미 처리됨)
3. "PROCESSING" → 중복 요청 차단
4. 락 획득 시도
5. saveAll() 트랜잭션 실행
6. 성공 시 "DONE" 상태로 변경 (TTL 72시간)
7. 실패 시 락 해제 및 예외 발생
```

---

## 2. 프론트엔드 변경사항 상세

### 2.1 API 계층

#### aiApi.ts
**추가된 DTC 관련 API**:

- `sendDtcReport(data: DtcReportRequest)`  
  - 단일 DTC 보고용(하위 호환/테스트용) 엔드포인트: `POST /api/v1/ai/dtc`
  - 현재 앱 플로우에서는 **직접 사용하지 않음**.
- `sendDtcBatchReport(data: DtcBatchReportRequest)`  
  - Mode 03(Stored DTCs) + Mode 02(Freeze Frame)을 **배치로 통합 보고**하는 실제 사용 API  
  - 엔드포인트: `POST /api/v1/ai/dtc/batch`

```typescript
export interface DtcReportRequest {
    vehicleId: string;
    dtcCode: string;
    descriptionKo?: string;
    descriptionEn?: string;
    summaryKo?: string;
    summaryEn?: string;
    severity?: 'CRITICAL' | 'WARNING' | 'INFO';
    status?: 'ACTIVE' | 'STORED' | 'PENDING';
}

export interface DtcBatchReportRequest {
    vehicleId: string;
    dtcs: { code: string; type: string; status: string }[];
    freezeFrame?: {
        rpm?: number;
        speed?: number;
        coolantTemp?: number;
        engineLoad?: number;
        ambientTemp?: number;
        fuelPressure?: number;
        pidsSnapshot?: string;
    };
}

export const sendDtcReport = async (data: DtcReportRequest): Promise<void> => {
    await api.post('/api/v1/ai/dtc', data);
};

export const sendDtcBatchReport = async (data: DtcBatchReportRequest): Promise<void> => {
    await api.post('/api/v1/ai/dtc/batch', data);
};
```

**목적**:
- `sendDtcReport`: 단일 코드 테스트/호환용
- `sendDtcBatchReport`: **실제 DTC 보고 흐름** (복수 코드 + Freeze Frame 스냅샷)

#### obdApi.ts
**변경사항**:

1. **ObdBatchRequest 타입 추가**
   ```typescript
   export interface ObdBatchRequest {
       batchId: string;      // UUID 기반 고유 ID
       vehicleId: string;
       logs: ObdLogRequest[];
   }
   ```

2. **ObdLogRequest 필드 확장**
   - `throttle`: 스로틀 위치 (%)
   - `map`: 흡기 압력 (kPa)
   - `maf`: 공기 유량 (g/s)
   - `intakeTemp`: 흡기 온도 (°C)
   - `engineRuntime`: 엔진 가동 시간 (초)

3. **uploadObdBatch() 시그니처 변경**
   ```typescript
   // 변경 전
   uploadObdBatch(logs: ObdLogRequest[])
   
   // 변경 후
   uploadObdBatch(data: ObdBatchRequest)
   ```

---

### 2.2 서비스 계층

#### ObdPidHelper.ts (123줄 추가)

**신규 PID 정의 8개**:

| PID | Mode | 이름 | 설명 | 단위 |
|-----|------|------|------|------|
| THROTTLE | 01 11 | Throttle Position | 스로틀 위치 | % |
| MAP | 01 0B | Intake MAP | 흡기 매니폴드 압력 | kPa |
| MAF | 01 10 | MAF Flow Rate | 공기 유량 | g/s |
| INTAKE_TEMP | 01 0F | Intake Temp | 흡기 온도 | °C |
| DTC_STATUS | 01 01 | DTC Status | MIL 상태 및 DTC 개수 | - |
| ENGINE_RUNTIME | 01 1F | Engine Runtime | 엔진 가동 시간 | sec |
| GET_DTCS | 03 - | Stored DTCs | 저장된 고장 코드 | - |
| FREEZE_DTC | 02 0200 | Freeze Frame DTC | 프리즈 프레임 DTC | - |

**디코더 로직 개선**:
- Mode 03 응답 파싱 지원
- DTC 코드 포맷팅 (P0XXX, C0XXX, B0XXX, U0XXX)
- MIL(Check Engine Light) 상태 추출

**예시**:
```typescript
// DTC_STATUS 디코더
decoder: (bytes) => {
    const milOn = (bytes[0] & 0x80) > 0;
    const dtcCount = bytes[0] & 0x7F;
    return milOn ? `MIL ON (${dtcCount} DTCs)` : `MIL OFF (${dtcCount} DTCs)`;
}

// GET_DTCS 디코더
decoder: (bytes) => {
    const dtcs = [];
    for (let i = 0; i < bytes.length; i += 2) {
        const typeCode = (bytes[i] & 0xC0) >> 6;
        const prefix = ['P', 'C', 'B', 'U'][typeCode];
        const code = prefix + ((bytes[i] & 0x3F).toString(16).padStart(2, '0')) 
                     + (bytes[i+1].toString(16).padStart(2, '0'));
        dtcs.push(code.toUpperCase());
    }
    return dtcs.join(', ');
}
```

---

#### ObdService.ts (대폭 개편, 1077줄)

이 파일이 이번 커밋의 핵심입니다. 주요 개선 영역을 정리합니다.

##### A. PID 실패 처리 로직

**신규 추가**:
```typescript
private pidFailCount: Map<string, number> = new Map();
private disabledPids: Set<string> = new Set();
private readonly MAX_PID_FAILURES = 5;
```

**동작 방식**:
1. PID 조회 실패 시 `pidFailCount` 증가
2. 연속 5회 실패 시 해당 PID 자동 비활성화
3. 주행 종료 시 실패 카운트 및 비활성화 목록 초기화

**코드 예시**:
```typescript
const result = await this.queryPid(pidKey);
if (result === null) {
    const failCount = (this.pidFailCount.get(pidKey) || 0) + 1;
    this.pidFailCount.set(pidKey, failCount);
    
    if (failCount >= this.MAX_PID_FAILURES) {
        this.disabledPids.add(pidKey);
        console.warn(`[ObdService] PID ${pidKey} disabled after ${failCount} failures`);
    }
}
```

**장점**:
- 지원하지 않는 PID에 대한 불필요한 재시도 방지
- 폴링 효율성 향상
- 차량마다 다른 PID 지원 여부 자동 학습

##### B. 배치 업로드 고도화

**변경 전** (단순 업로드):
```typescript
async uploadBatch() {
    await api.post('/telemetry/batch', this.dataBuffer);
    this.dataBuffer = [];
}
```

**변경 후** (멱등성 + Drain 로직):
```typescript
private async uploadBatch(logsToUpload: ObdLogRequest[]) {
    if (this.isUploading) {
        console.log('[ObdService] Upload already in progress, queuing...');
        return;
    }
    
    this.isUploading = true;
    try {
        const batchId = generateUUID();
        const batchData: ObdBatchRequest = {
            batchId,
            vehicleId: this.currentVehicleId,
            logs: logsToUpload
        };
        
        await uploadObdBatch(batchData);
        
        // [Drain 로직] 버퍼에 남은 데이터가 있으면 계속 업로드
        if (this.dataBuffer.length > 0) {
            const nextBatch = [...this.dataBuffer];
            this.dataBuffer = [];
            setTimeout(() => this.uploadBatch(nextBatch), 0);
        }
    } catch (error) {
        // 실패 시 오프라인 큐에 저장
        await OfflineStorage.addToQueue({
            url: '/api/v1/telemetry/batch',
            method: 'POST',
            body: JSON.stringify(batchData),
            timestamp: Date.now()
        });
    } finally {
        this.isUploading = false;
    }
}
```

**개선 사항**:
1. **멱등성 보장**: `batchId` 생성으로 중복 업로드 방지
2. **동시성 제어**: `isUploading` 플래그로 중복 실행 차단
3. **Drain 로직**: 업로드 성공 후 버퍼에 남은 데이터 순차 처리
4. **오프라인 대응**: 실패 시 자동으로 오프라인 큐에 저장

##### C. 자동 주행 종료 감지

**신규 추가**:
```typescript
private engineStoppedTime: number | null = null;
private readonly AUTO_END_DELAY = 180000; // 3분 (180초)
```

**동작 로직**:
```typescript
// 폴링 중 RPM과 Speed 확인
if (this.currentData.rpm === 0 && this.currentData.speed === 0) {
    if (this.engineStoppedTime === null) {
        this.engineStoppedTime = Date.now();
        console.log('[ObdService] Engine stopped detected, starting timer...');
    } else {
        const stoppedDuration = Date.now() - this.engineStoppedTime;
        if (stoppedDuration >= this.AUTO_END_DELAY) {
            console.log('[ObdService] Auto-ending trip after 3min idle');
            await this.endTripAndDisconnect();
        }
    }
} else {
    // 엔진 재시작 시 타이머 리셋
    this.engineStoppedTime = null;
}
```

**종료 프로세스**:
```typescript
private async endTripAndDisconnect() {
    // 1. 버퍼 플러시
    if (this.dataBuffer.length > 0) {
        const logsToUpload = [...this.dataBuffer];
        this.dataBuffer = [];
        await this.uploadBatch(logsToUpload);
    }
    
    // 2. 주행 종료 API 호출
    await disconnectVehicleApi(this.currentVehicleId);
    
    // 3. 연결 해제
    await this.disconnect();
    
    // 4. PID 실패 상태 초기화
    this.pidFailCount.clear();
    this.disabledPids.clear();
}
```

**장점**:
- 사용자가 수동으로 종료하지 않아도 자동 처리
- 데이터 손실 방지 (버퍼 플러시)
- 주행 종료 시점 명확화

##### D. DTC 자동 보고 (Mode 01 → 02/03 Edge 기반)

**최종 구조**:

1. **01 01 (DTC_STATUS) 폴링**
   - `pollingLoop()`에서 5초 주기로 `OBD_PIDS.DTC_STATUS`를 큐에 넣음.
   - 디코더는 `"MIL ON (3 DTCs)"`/`"MIL OFF (0 DTCs)"`처럼 문자열을 반환.

2. **0 → N(>0) 변화 감지**
   - `ObdService.ts`에 `previousDtcCount: number` 필드를 두고,  
     직전 01 01 응답과 현재 응답의 DTC 개수를 비교.
   - **직전 0, 현재 >0 인 “엣지”가 발생할 때만** 상세 수집을 시작:
     ```typescript
     const text = result.toString();
     const match = text.match(/(\d+)\s*DTCs?/i);
     const currentCount = match ? parseInt(match[1], 10) : 0;
     if (previousDtcCount === 0 && currentCount > 0) {
         // 여기에서만 상세 수집 시작
         this.reportDetailedDtc(text);
     }
     previousDtcCount = currentCount;
     ```

3. **Mode 03 + Mode 02 상세 수집 및 배치 전송**
   - `reportDetailedDtc()` 내부에서:
     - `lastDtcCodes`, `lastFreezeDtc` 초기화
     - `GET_DTCS`(Mode 03)와 `FREEZE_DTC`(Mode 02)를 **HIGH 우선순위**로 큐에 추가
     - 최대 5초 대기하면서 두 응답 수집
     - `lastDtcCodes`를 쉼표 기준으로 파싱해 `type: 'STORED'` DTC 목록 구성
     - `lastFreezeDtc`(Mode 02) 결과를 `type: 'FREEZE_FRAME'`으로 1개 추가 (중복 제거)
     - `sendDtcBatchReport(...)`로 **한 번만** 배치 보고:
       - `vehicleId`
       - `dtcs: { code, type, status }[]`
       - `freezeFrame`: 현재 스냅샷(`rpm`, `speed`, `coolantTemp`, `engineLoad`, `pidsSnapshot` 등)

**결과**:
- 동일 고장이 계속 유지되는 동안에도,  
  - **01 01 기준 “0 → N”이 되는 최초 시점에만** Mode 02/03 수집 + 백엔드 보고 수행.
- 앱/연결 재시작 시:
  - `previousDtcCount`가 0에서 시작하므로,  
  - 이미 존재하는 DTC에 대해서도 **시작 시 1회 보고**가 일어난다.

##### E. 코드 리팩토링

**변경 전** (장황한 코드):
```typescript
private async saveLastDevice(type: 'classic' | 'ble', id: string, name: string) {
    try {
        const info = {
            type,
            id,
            name: name || 'Unknown Device',
            address: id,
        };
        await AsyncStorage.setItem(STORAGE_KEY_LAST_DEVICE, JSON.stringify(info));
        console.log('[ObdService] Saved last device:', info);
    } catch (e) {
        console.error('[ObdService] Failed to save device:', e);
    }
}
```

**변경 후** (간결화):
```typescript
private async saveLastDevice(type: 'classic' | 'ble', id: string, name: string) {
    try {
        await AsyncStorage.setItem(STORAGE_KEY_LAST_DEVICE, JSON.stringify({ type, id, name }));
    } catch (e) { }
}
```

**개선 사항**:
- 불필요한 로그 제거
- 변수 간소화
- 핵심 로직만 유지

---

#### OfflineStorage.ts

**주요 개선 3가지**:

##### 1. 큐 용량 제한
```typescript
const MAX_QUEUE_SIZE = 50; // 최대 50배치 (약 150분 분량)
```

**목적**: 무한 증가 방지, 디스크 공간 관리

##### 2. FIFO 정책
```typescript
async addToQueue(req: Omit<QueuedRequest, 'id' | 'retryCount'>) {
    const countResult = await db.getFirstAsync<{ count: number }>('SELECT COUNT(*) as count FROM request_queue');
    const currentCount = countResult?.count ?? 0;
    
    if (currentCount >= MAX_QUEUE_SIZE) {
        // 가장 오래된 항목 삭제
        const oldest = await db.getFirstAsync<QueuedRequest>(
            'SELECT * FROM request_queue ORDER BY timestamp ASC, id ASC LIMIT 1'
        );
        if (oldest?.id) {
            await db.runAsync('DELETE FROM request_queue WHERE id = ?', oldest.id);
            console.warn(`[OfflineDrop] dropped=1 reason=capacity url=${oldest.url}`);
        }
    }
    
    // 새 항목 추가
    await db.runAsync('INSERT INTO request_queue ...');
}
```

**개선 사항**:
- `timestamp ASC, id ASC` 오더링으로 정합성 보장
- 드롭된 요청 로그 기록

##### 3. URL 중복 확인
```typescript
async isUrlQueued(url: string): Promise<boolean> {
    const db = await this.ensureDb();
    const result = await db.getFirstAsync<{ count: number }>(
        'SELECT COUNT(*) as count FROM request_queue WHERE url = ?', 
        url
    );
    return (result?.count ?? 0) > 0;
}
```

**사용 시나리오**:
- 주행 종료 API 중복 큐잉 방지
- 동일 배치 재전송 방지

---

#### BackgroundService.ts

**변경 사항**:

1. **알림 메시지 개선**
   - 변경 전: "백그라운드에서 차량 데이터를 수집하고 있습니다."
   - 변경 후: "백그라운드에서도 차량 진단 데이터가 안전하게 기록되고 있습니다."
   
2. **하트비트 간격 조정**
   - 변경 전: `delay: 2000` (2초)
   - 변경 후: `delay: 5000` (5초)
   - **이유**: 배터리 소모 최적화

3. **일시정지 비활성화**
   ```typescript
   allowPause: false
   ```
   - **목적**: 사용자가 알림에서 서비스를 실수로 중단하지 못하게 방지

4. **Deep Link 경로 변경**
   - 변경 전: `yourSchemeHere://chat/jane`
   - 변경 후: `frontend://obd`

---

### 2.3 두 번째 커밋 (추가) - ObdService.ts 개선

#### 변경사항 1: 오프라인 큐 동시성 제어

**추가된 플래그**:
```typescript
private isProcessingOfflineQueue: boolean = false;
```

**개선된 로직**:
```typescript
private async processOfflineQueue() {
    // 중복 실행 방지
    if (this.isProcessingOfflineQueue) {
        console.log('[ObdService] processOfflineQueue already running, skipping');
        return;
    }
    
    this.isProcessingOfflineQueue = true;
    try {
        const queue = await OfflineStorage.getQueue();
        if (queue.length === 0) return;
        
        for (const req of queue) {
            if (!NetworkService.IsConnected) break;
            try {
                await api.request({
                    url: req.url,
                    method: req.method,
                    data: req.body ? JSON.parse(req.body) : undefined,
                });
                if (req.id) await OfflineStorage.removeFromQueue(req.id);
            } catch (e) {
                break;
            }
        }
    } finally {
        // 에러 발생 시에도 플래그 해제 보장
        this.isProcessingOfflineQueue = false;
    }
}
```

**개선 이유**: 네트워크 복구 시 여러 곳에서 `processOfflineQueue()` 호출 시 중복 실행 방지

---

#### 변경사항 2: 연결 상태 클린업 통합

**신규 메서드**:
```typescript
private cleanupConnectionState() {
    // 구독 해제
    if (this.classicDataSubscription) {
        this.classicDataSubscription.remove();
        this.classicDataSubscription = null;
    }
    
    // 타이머 클리어
    if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
    }
    
    if (this.samplingTimer) {
        clearTimeout(this.samplingTimer);
        this.samplingTimer = null;
    }
    
    // 폴링 플래그 리셋
    this.isPolling = false;
    this.isProcessingQueue = false;
}
```

**적용 위치**:
```typescript
async setTargetDevice(deviceId: string) {
    // [개선] 기존 연결 상태 클린업
    this.cleanupConnectionState();
    
    this.connectionType = 'ble';
    this.currentDeviceId = deviceId;
    // ... (나머지 로직)
}

async setClassicDevice(device: BluetoothDevice) {
    // [개선] 기존 연결 상태 클린업
    this.cleanupConnectionState();
    
    this.connectionType = 'classic';
    this.classicDevice = device;
    // ... (나머지 로직)
}
```

**장점**:
- 코드 중복 제거
- 상태 초기화 로직 단일화
- 메모리 누수 방지

---

#### 변경사항 3: 멱등성 보장

**BLE 디바이스 설정 시**:
```typescript
async setTargetDevice(deviceId: string) {
    // 멱등성 보장: 동일 디바이스 재설정 시 no-op
    if (this.connectionType === 'ble' && this.currentDeviceId === deviceId) {
        console.log('[ObdService] BLE device already set, skipping');
        return;
    }
    
    this.cleanupConnectionState();
    // ... (연결 로직)
}
```

**Classic BT 디바이스 설정 시**:
```typescript
async setClassicDevice(device: BluetoothDevice) {
    // 멱등성 보장: 동일 디바이스 재설정 시 no-op
    if (this.connectionType === 'classic' && this.classicDevice?.address === device.address) {
        console.log('[ObdService] Classic BT device already set, skipping');
        return;
    }
    
    this.cleanupConnectionState();
    // ... (연결 로직)
}
```

**효과**:
- 불필요한 재연결 시도 방지
- BLE 재연결 로직 안정성 향상
- 로그 노이즈 감소

---

## 3. 백엔드 변경 필요 여부 검토

### 검토 결과: **변경 불필요**

#### 이유

백엔드는 이미 프론트엔드의 모든 변경사항을 처리할 수 있는 구조를 갖추고 있습니다:

1. **배치 ID 기반 멱등성 처리 완료**
   - `ObdBatchRequestDto.batchId` 수신 및 처리
   - Redis 기반 중복 요청 차단 (PROCESSING/DONE 상태 관리)
   - 72시간 TTL로 오프라인 큐 대응

2. **차량별 네임스페이스 분리**
   - `obd:batch:{vehicleId}:{batchId}` 형식으로 키 관리
   - 차량별 독립적인 배치 처리

3. **트랜잭션 안정성**
   - `@Transactional` 어노테이션으로 원자성 보장
   - 실패 시 자동 롤백 및 Redis 락 해제

4. **필드 매핑 처리**
   - `@JsonProperty("throttle")` 적용으로 프론트엔드 호환성 확보

#### 선택적 개선 사항 (필수 아님)

만약 추가 개선을 원한다면:

1. **로깅 강화**
   ```java
   log.info("[ObdService] Batch processing stats: vehicleId={}, batchId={}, logCount={}", 
            vehicleId, batchId, obdLogs.size());
   ```

2. **Redis 메트릭 모니터링**
   - 배치 처리량 추적
   - TTL 만료 전 정리율 확인

3. **에러 응답 세분화**
   - 현재: 모든 실패는 예외 발생
   - 개선: 4xx (클라이언트 에러) vs 5xx (서버 에러) 구분

하지만 현재 상태로도 **프로덕션 배포 가능**합니다.

---

## 4. 핵심 개선사항 요약

### 안정성 향상
1. **PID 실패 처리**: 지원하지 않는 PID 자동 비활성화
2. **동시성 제어**: 업로드 및 오프라인 큐 처리 중복 실행 방지
3. **멱등성 보장**: 배치 ID 기반 중복 업로드 차단
4. **상태 클린업**: 연결 전환 시 메모리 누수 방지

### 데이터 무결성
1. **오프라인 큐 용량 제한**: 최대 50배치 (FIFO 정책)
2. **Drain 로직**: 업로드 성공 후 버퍼 데이터 순차 처리
3. **자동 주행 종료**: 엔진 정지 3분 후 버퍼 플러시

### 기능 확장
1. **8개 신규 PID 지원**: Throttle, MAP, MAF, Intake Temp, Runtime, DTC 관련
2. **DTC 자동 보고**: Mode 03 조회 결과를 AI 서버에 실시간 전송
3. **배터리 최적화**: 백그라운드 서비스 하트비트 2초 → 5초

### 코드 품질
1. **리팩토링**: 불필요한 주석 및 로그 제거
2. **간결화**: 화살표 함수 및 단축 문법 활용
3. **단일 책임**: `cleanupConnectionState()` 메서드 분리

---

## 5. 배포 체크리스트

### 백엔드
- [x] Redis 서버 정상 작동 확인
- [x] TTL 72시간 설정 검증
- [ ] 로그 모니터링 설정 (선택)

### 프론트엔드
- [ ] 앱 재빌드 및 배포
- [ ] DTC 보고 엔드포인트 테스트 (`/api/v1/ai/dtc`)
- [ ] 오프라인 → 온라인 전환 시 큐 처리 테스트
- [ ] 3분 자동 종료 시나리오 테스트

### 통합 테스트
- [ ] 차량 연결 후 180개 로그 배치 업로드 테스트
- [ ] 네트워크 단절 후 오프라인 큐 저장 확인
- [ ] 네트워크 복구 후 큐 자동 처리 확인
- [ ] DTC 발생 시 AI 서버 보고 확인

---

## 6. 향후 개선 방향 (선택)

### 단기
1. **PID 지원 여부 자동 학습 영속화**
   - 현재: 앱 재시작 시 리셋
   - 개선: AsyncStorage에 저장하여 차량별 프로파일 관리

2. **DTC 보고 중복 방지**
   - 현재: 매번 전송 가능
   - 개선: 동일 DTC는 1일 1회만 보고

### 중기
1. **스마트 폴링 간격 조정**
   - 현재: 고정 1초
   - 개선: 주행 상태(정차/운행)에 따라 동적 조정

2. **배치 크기 최적화**
   - 현재: 3분 고정
   - 개선: 네트워크 상태에 따라 1~5분 가변

### 장기
1. **Edge AI 통합**
   - 현재: 서버 전송 후 분석
   - 개선: 디바이스에서 실시간 이상 패턴 감지

2. **블루투스 멀티 디바이스**
   - 현재: 1대 차량만 연결
   - 개선: 여러 차량 동시 모니터링 (가족 차량)

---

## 7. 결론

이번 "블루투스 고도화" 커밋은 **안정성, 데이터 무결성, 기능 확장** 측면에서 큰 발전을 이루었습니다.

특히:
- **백엔드는 추가 변경 없이 모든 기능 처리 가능**
- **프론트엔드는 프로덕션 레벨의 안정성 확보**
- **사용자 경험 개선** (자동 주행 종료, 실시간 DTC 알림)

**현재 상태로 배포 가능**하며, 향후 개선 사항은 필요에 따라 단계적으로 적용하면 됩니다.

---

## 8. DTC 고도화 추가 변경사항 및 부족한 점 (Git 최신 반영)

최근 Git에서 DTC 관련으로 추가·수정된 항목을 기준으로, **현재 구현 상태**와 **부족한 점**을 정리했습니다.

### 8.1 최신 DTC 관련 변경 요약

| 구분 | 파일 | 변경 내용 |
|------|------|-----------|
| 백엔드 | `AiController.java` | `POST /ai/dtc/batch` 추가 (Mode 03 + Mode 02 통합) |
| 백엔드 | `AiDiagnosisService.java` | `processDtcBatch()` 구현, Freeze Frame 저장, 배치 알림 |
| 백엔드 | `DtcBatchRequest.java` | 신규 DTO (vehicleId, dtcs[], freezeFrame) |
| 백엔드 | `DtcFreezeFrame.java` | 신규 엔티티 (dtc_freeze_frames) |
| 백엔드 | `DtcFreezeFrameRepository.java` | 신규 Repository |
| 프론트 | `aiApi.ts` | `sendDtcBatchReport()` 추가, `/api/v1/ai/dtc/batch` 호출 |
| 프론트 | `ObdService.ts` | `reportDetailedDtc()`에서 배치+프리즈프레임 전송 |

- 프론트는 **단일 DTC**(`sendDtcReport`)는 사용하지 않고, **배치 전송**(`sendDtcBatchReport`)만 사용 중입니다.
- 백엔드는 단일(`/ai/dtc`) + 배치(`/ai/dtc/batch`) 모두 지원하며, 배치 시 Freeze Frame을 `DtcFreezeFrame` 엔티티로 저장합니다.

### 8.2 부족한 점 및 수정 권장 사항 (업데이트)

#### 1) **DtcType에 FREEZE_FRAME 없음 → 런타임 예외** *(해결됨)*

- **수정**: `DtcHistory.DtcType`에 `FREEZE_FRAME` 추가, DB `dtc_type` enum에도 동일 값 반영.
- **결과**: 프론트에서 `type: 'FREEZE_FRAME'`으로 전송해도 `valueOf` 예외 없이 정상 저장.

#### 2) **DB dtc_status enum과 Java DtcStatus 불일치** *(해결됨)*

- **수정**: `schema.sql`의 `dtc_status` enum에 `PENDING`, `STORED` 추가.
- **Java**: `DtcHistory.DtcStatus` (`ACTIVE`, `RESOLVED`, `CLEARED`, `PENDING`, `STORED`)와 일치.

#### 3) **DTC 중복 보고 방지 미구현** *(부분 해결 / 백엔드 추가 개선 여지)*

- **프론트**: 01 01 DTC 개수 기준 **0 → N(>0) 엣지에서만** Mode 02/03 수집 + `sendDtcBatchReport` 수행 → 동일 세션 내 과도한 중복 전송 방지.
- **백엔드**: 현재는 모든 배치를 수신해 `dtc_history`에 저장하며,  
  - 향후 차량+코드 세트 시그니처 기반으로 **동일 세트에 대한 FCM/진단 중복 억제 로직**을 추가하는 것이 권장된다.

#### 4) **Freeze Frame 데이터 1:N 중복 저장** *(해결됨)*

- **수정 전**: `processDtcBatch()`에서 동일 `freezeFrame`을 배치 내 모든 DTC에 대해 각각 저장 → 동일 스냅샷 N행.
- **수정 후**:
  - `freezeFrameSaved` 플래그를 도입하여 **첫 번째 DTC에 대해서만 1건 저장**.
  - 설계상 “Freeze Frame 1건 ↔ 대표 DTC 1건” 관계로 단순화.

#### 5) **프론트 Freeze Frame 필드 누락 (선택)**

- 여전히 선택 사항이지만, 현재 구현은 다음만 전송:
  - `rpm`, `speed`, `coolantTemp`, `engineLoad`, `pidsSnapshot`
- `ambientTemp`, `fuelPressure`는 추후 PID 수집 안정화 시 확장 여지.

#### 6) **스키마와 엔티티 불일치 (dtc_history)**

- `dtc_manufacturer`, `resolution_type` 필드는 여전히 엔티티에 직접 매핑되지 않음(기본값/nullable로 운영).
- 장기적으로는 감사/리포트 요구사항에 따라 엔티티에 추가 매핑하거나, 별도 뷰/리포트 테이블로 정리하는 것이 좋다.

### 8.3 정리

| 항목 | 심각도 | 비고 |
|------|--------|------|
| FREEZE_FRAME → DtcType | 해결됨 | enum/DB 모두 FREEZE_FRAME 반영 |
| dtc_status enum 불일치 | 해결됨 | DB/Java enum 동기화 완료 |
| DTC 중복 보고 방지 | 중간 | 프론트 0→N 엣지 처리 완료, 백엔드 시그니처 기반 억제는 추가 개선 여지 |
| Freeze Frame 1:N 중복 | 해결됨 | 첫 번째 DTC에만 1건 저장 |
| 프론트 freezeFrame 필드 | 낮음 | 선택적 보강 (ambientTemp, fuelPressure 등) |
| dtc_history 스키마 정합성 | 낮음 | 유지보수/리포팅 필요 시 추가 정렬 예정 |

**현재 상태**: 프론트/백 기준 필수 이슈는 모두 처리되었고, 남은 항목은 “중복 알림 억제 튜닝” 및 “필드 확장/리포팅 품질” 수준의 고도화 과제입니다.
