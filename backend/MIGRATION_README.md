# 소모품 마모 계수 계산 시스템 - 규칙 기반 마이그레이션

## 아키텍처 변경

### Before (AI 서버 의존)
```
Backend (Java) → AI Server (Python/FastAPI) → 규칙 기반 계산
```

### After (순수 Java 백엔드)
```
Backend (Java) → 규칙 기반 계산 (WearFactorService 내부)
```

## 마모 계수 공식 (5개 소모품)

### 1. 타이어 (Tire)
```
factor = 1.0 + (hard_accel + hard_brake) × 0.03
factor = min(factor, 3.0)
```

### 2. 엔진오일 (Engine Oil)
```
cold_penalty = 1.5 (if distance < 5km, else 1.0)
rpm_penalty  = 1.0 + high_rpm_ratio × 0.8
idle_penalty = 1.0 + idle_ratio × 0.5
factor = cold × rpm × idle
factor = min(factor, 2.5)
```

### 3. 냉각수 (Coolant) - Arrhenius 방정식
```
factor = 2 ^ (max(0, max_temp - 90) / 10)
```

### 4. 에어필터 (Air Filter)
```
efficiency = avg_maf / (baseline_maf × avg_throttle)
factor = 1.5 ^ (max(0, 1.0 - efficiency) / 0.1)
```

### 5. 브레이크패드 (Brake Pad)
```
brake_energy = hard_brake × avg_speed² / 10000
city_mult = 1.3 (if avg_speed < 30, else 1.0)
factor = (1.0 + brake_energy) × city_mult
```

## 주요 파일

| 파일 | 역할 |
|------|------|
| `ConsumableConstants.java` | 상수 정의 (주기, 계수, 임계값) |
| `ConsumableType.java` | 소모품 타입 열거형 |
| `RecommendationType.java` | 교체 권고 수준 열거형 |
| `WearFactorService.java` | 마모 계수 계산 (규칙 기반) |
| `TripService.java` | 주행 통계 및 호출 |
| `WearFactorServiceTest.java` | 공식 단위 테스트 (20개) |

## 테스트 실행
```bash
./gradlew test --tests "kr.co.himedia.service.WearFactorServiceTest"
```
