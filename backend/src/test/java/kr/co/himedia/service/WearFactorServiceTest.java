package kr.co.himedia.service;

import java.time.LocalDateTime;

import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.ConsumableItemRepository;
import kr.co.himedia.repository.ObdLogRepository;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.*;

/**
 * WearFactorService 단위 테스트
 * Python 공식과 동일한 결과를 반환하는지 검증합니다.
 */
@ExtendWith(MockitoExtension.class)
class WearFactorServiceTest {

    @InjectMocks
    private WearFactorService wearFactorService;

    @Mock
    private VehicleRepository vehicleRepository;
    @Mock
    private VehicleConsumableRepository vehicleConsumableRepository;
    @Mock
    private ConsumableItemRepository consumableItemRepository;
    @Mock
    private NotificationService notificationService;
    @Mock
    private UserRepository userRepository;
    @Mock
    private ObdLogRepository obdLogRepository;

    // ==================== 1. 타이어 테스트 ====================

    @Nested
    @DisplayName("타이어 마모 계수 (Tire Factor)")
    class TireFactorTests {

        @Test
        @DisplayName("기본 케이스: accel=10, brake=5 → factor=1.45")
        void testTireFactorBasicCase() {
            // Python: 1.0 + (10 + 5) * 0.03 = 1.45
            TripSummary trip = createTripWithAccelBrake(10, 5);
            Double factor = invokeCalculateTireFactor(trip);
            assertEquals(1.45, factor, 0.001);
        }

        @Test
        @DisplayName("최대 캡: accel=50, brake=50 → factor=3.0 (max)")
        void testTireFactorMaxCap() {
            // Python: 1.0 + (50 + 50) * 0.03 = 4.0 → min(4.0, 3.0) = 3.0
            TripSummary trip = createTripWithAccelBrake(50, 50);
            Double factor = invokeCalculateTireFactor(trip);
            assertEquals(3.0, factor, 0.001);
        }

        @Test
        @DisplayName("급가속/급제동 없음: accel=0, brake=0 → factor=1.0")
        void testTireFactorNoEvents() {
            TripSummary trip = createTripWithAccelBrake(0, 0);
            Double factor = invokeCalculateTireFactor(trip);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("Null 처리: accel=null, brake=null → factor=1.0")
        void testTireFactorNullValues() {
            TripSummary trip = TripSummary.builder().build();
            Double factor = invokeCalculateTireFactor(trip);
            assertEquals(1.0, factor, 0.001);
        }
    }

    // ==================== 1-b. 공회전 비율 테스트 ====================

    @Nested
    @DisplayName("공회전 비율 계산 (calculateIdleRatio)")
    class IdleRatioTests {

        @Test
        @DisplayName("정상 케이스: idleTime=300, duration=600 → ratio=0.5")
        void testIdleRatioNormalCase() {
            TripSummary trip = createTripWithIdleAndDuration(300, 600);
            Double ratio = invokeCalculateIdleRatio(trip);
            assertEquals(0.5, ratio, 0.001);
        }

        @Test
        @DisplayName("제로 duration: startTime=endTime → ratio=0.0")
        void testIdleRatioZeroDuration() {
            LocalDateTime now = LocalDateTime.of(2026, 1, 1, 12, 0, 0);
            TripSummary trip = TripSummary.builder()
                    .startTime(now)
                    .endTime(now)
                    .idleTime(100)
                    .build();
            Double ratio = invokeCalculateIdleRatio(trip);
            assertEquals(0.0, ratio, 0.001);
        }

        @Test
        @DisplayName("Null 입력: startTime/endTime null → ratio=0.0")
        void testIdleRatioNullInput() {
            TripSummary trip = TripSummary.builder().idleTime(100).build();
            Double ratio = invokeCalculateIdleRatio(trip);
            assertEquals(0.0, ratio, 0.001);
        }
    }

    // ==================== 2. 엔진오일 테스트 ====================

    @Nested
    @DisplayName("엔진오일 마모 계수 (Engine Oil Factor)")
    class EngineOilFactorTests {

        @Test
        @DisplayName("냉간 시동: distance=3km → cold_penalty=1.5")
        void testEngineOilColdStart() {
            // Python: cold=1.5, rpm=(1+0*0.8)=1.0, idle=(1+0*0.5)=1.0 → 1.5
            TripSummary trip = createTripWithDistance(3.0);
            Double factor = invokeCalculateEngineOilFactor(trip, 0.0, 0.0);
            assertEquals(1.5, factor, 0.001);
        }

        @Test
        @DisplayName("정상 주행: distance=10km → cold_penalty=1.0")
        void testEngineOilNormalStart() {
            // Python: cold=1.0, rpm=(1+0*0.8)=1.0, idle=(1+0*0.5)=1.0 → 1.0
            TripSummary trip = createTripWithDistance(10.0);
            Double factor = invokeCalculateEngineOilFactor(trip, 0.0, 0.0);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("고RPM: highRpmRatio=0.5 → rpm_penalty=1.4")
        void testEngineOilHighRpm() {
            // Python: cold=1.0, rpm=(1+0.5*0.8)=1.4, idle=(1+0*0.5)=1.0 → 1.4
            TripSummary trip = createTripWithDistance(10.0);
            Double factor = invokeCalculateEngineOilFactor(trip, 0.5, 0.0);
            assertEquals(1.4, factor, 0.001);
        }

        @Test
        @DisplayName("공회전: idleRatio=0.3 → idle_penalty=1.15")
        void testEngineOilIdlePenalty() {
            // Python: cold=1.0, rpm=1.0, idle=(1+0.3*0.5)=1.15 → 1.15
            TripSummary trip = createTripWithDistance(10.0);
            Double factor = invokeCalculateEngineOilFactor(trip, 0.0, 0.3);
            assertEquals(1.15, factor, 0.001);
        }

        @Test
        @DisplayName("복합 패널티: cold=1.5 * rpm=1.4 * idle=1.15 = 2.415")
        void testEngineOilCombined() {
            // Python: 1.5 * 1.4 * 1.15 = 2.415
            TripSummary trip = createTripWithDistance(3.0);
            Double factor = invokeCalculateEngineOilFactor(trip, 0.5, 0.3);
            assertEquals(2.415, factor, 0.001);
        }

        @Test
        @DisplayName("최대 캡: factor ≤ 2.5")
        void testEngineOilMaxCap() {
            // Python: 1.5 * (1+0.8*0.8) * (1+0.9*0.5) = 1.5 * 1.64 * 1.45 = 3.567 →
            // min(3.567, 2.5) = 2.5
            TripSummary trip = createTripWithDistance(3.0);
            Double factor = invokeCalculateEngineOilFactor(trip, 0.8, 0.9);
            assertEquals(2.5, factor, 0.001);
        }

        @Test
        @DisplayName("모든 값 Null: distance=null, highRpmRatio=null, idleRatio=null → factor=1.0")
        void testEngineOilAllNull() {
            // distance=null → cold_penalty=1.0 (null이므로 < 5 조건 false)
            // highRpmRatio=null → 0.0, idleRatio=null → 0.0
            // factor = 1.0 * 1.0 * 1.0 = 1.0
            TripSummary trip = TripSummary.builder().build();
            Double factor = invokeCalculateEngineOilFactor(trip, null, null);
            assertEquals(1.0, factor, 0.001);
        }
    }

    // ==================== 3. 냉각수 테스트 ====================

    @Nested
    @DisplayName("냉각수 마모 계수 (Coolant Factor)")
    class CoolantFactorTests {

        @Test
        @DisplayName("정상 온도: 90°C 이하 → factor=1.0")
        void testCoolantNormalTemp() {
            TripSummary trip = createTripWithMaxCoolantTemp(85.0);
            Double factor = invokeCalculateCoolantFactor(trip);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("정확히 90°C → factor=1.0")
        void testCoolantExactly90() {
            TripSummary trip = createTripWithMaxCoolantTemp(90.0);
            Double factor = invokeCalculateCoolantFactor(trip);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("Arrhenius: 100°C → factor=2.0 (2^1)")
        void testCoolantArrhenius100() {
            // Python: 2 ^ ((100-90)/10) = 2 ^ 1 = 2.0
            TripSummary trip = createTripWithMaxCoolantTemp(100.0);
            Double factor = invokeCalculateCoolantFactor(trip);
            assertEquals(2.0, factor, 0.001);
        }

        @Test
        @DisplayName("Arrhenius: 110°C → factor=4.0 (2^2)")
        void testCoolantArrhenius110() {
            // Python: 2 ^ ((110-90)/10) = 2 ^ 2 = 4.0
            TripSummary trip = createTripWithMaxCoolantTemp(110.0);
            Double factor = invokeCalculateCoolantFactor(trip);
            assertEquals(4.0, factor, 0.001);
        }

        @Test
        @DisplayName("Null 처리: maxCoolantTemp=null → factor=1.0")
        void testCoolantNullTemp() {
            TripSummary trip = TripSummary.builder().build();
            Double factor = invokeCalculateCoolantFactor(trip);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("극단 온도: 200°C → 상한(4.0) 적용, 유한값 반환")
        void testCoolantExtremeTemp() {
            // raw: 2 ^ ((200-90)/10) = 2^11 = 2048.0 → COOLANT_MAX_FACTOR(4.0) 적용
            TripSummary trip = createTripWithMaxCoolantTemp(200.0);
            Double factor = invokeCalculateCoolantFactor(trip);
            assertNotNull(factor);
            assertFalse(factor.isInfinite(), "Factor should not be Infinity");
            assertFalse(factor.isNaN(), "Factor should not be NaN");
            assertEquals(4.0, factor, 0.001);
        }
    }

    // ==================== 4. 에어필터 테스트 ====================

    @Nested
    @DisplayName("에어필터 마모 계수 (Air Filter Factor)")
    class AirFilterFactorTests {

        @Test
        @DisplayName("정상 효율: efficiency=1.0 → factor=1.0")
        void testAirFilterNormalEfficiency() {
            // avgMaf=18, baseline=18(default), throttle=100% → efficiency=18/(18*1.0)=1.0
            // factor = 1.5 ^ (max(0, 1.0-1.0)/0.1) = 1.5^0 = 1.0
            TripSummary trip = createTripWithMafThrottle(18.0, 100.0);
            Vehicle vehicle = createVehicleWithModel("unknown"); // baseline=18.0 (default)
            Double factor = invokeCalculateAirFilterFactor(trip, vehicle);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("효율 저하: efficiency=0.8 → factor 계산")
        void testAirFilterReducedEfficiency() {
            // avgMaf=14.4, baseline=18(default), throttle=100% → efficiency=14.4/(18*1.0)=0.8
            // loss=0.2, factor = 1.5 ^ (0.2/0.1) = 1.5^2 = 2.25
            TripSummary trip = createTripWithMafThrottle(14.4, 100.0);
            Vehicle vehicle = createVehicleWithModel("unknown");
            Double factor = invokeCalculateAirFilterFactor(trip, vehicle);
            assertEquals(2.25, factor, 0.001);
        }

        @Test
        @DisplayName("스로틀 정규화: throttle 50% (0~100 → 0~1)")
        void testAirFilterThrottleNormalization() {
            // avgMaf=9, baseline=18(default), throttle=50% → normalized=0.5
            // efficiency = 9 / (18 * 0.5) = 1.0 → factor = 1.0
            TripSummary trip = createTripWithMafThrottle(9.0, 50.0);
            Vehicle vehicle = createVehicleWithModel("unknown");
            Double factor = invokeCalculateAirFilterFactor(trip, vehicle);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("MAF null (EV 차량) → factor=1.0 (주행거리만 반영)")
        void testAirFilterNullMaf() {
            TripSummary trip = TripSummary.builder().build();
            Vehicle vehicle = createVehicleWithModel("unknown");
            Double factor = invokeCalculateAirFilterFactor(trip, vehicle);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("차량 모델별 기준 MAF: Sonata 2.0 → baseline=18.0")
        void testAirFilterSonataBaseline() {
            // avgMaf=18, baseline(Sonata)=18, throttle=100% → efficiency=1.0 → factor=1.0
            TripSummary trip = createTripWithMafThrottle(18.0, 100.0);
            Vehicle vehicle = createVehicleWithModel("Sonata 2.0");
            Double factor = invokeCalculateAirFilterFactor(trip, vehicle);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("극단 MAF: avgMaf=1.0, throttle=100% → Infinity/NaN 없이 유한값 반환")
        void testAirFilterExtremeValues() {
            // efficiency = 1.0 / (16 * 1.0) = 0.0625
            // loss = 1.0 - 0.0625 = 0.9375
            // factor = 1.5 ^ (0.9375 / 0.1) = 1.5 ^ 9.375 → 유한값
            TripSummary trip = createTripWithMafThrottle(1.0, 100.0);
            Vehicle vehicle = createVehicleWithModel("unknown");
            Double factor = invokeCalculateAirFilterFactor(trip, vehicle);
            assertNotNull(factor);
            assertFalse(factor.isInfinite(), "Factor should not be Infinity");
            assertFalse(factor.isNaN(), "Factor should not be NaN");
            assertTrue(factor > 1.0, "Factor should be greater than 1.0 for degraded efficiency");
        }
    }

    // ==================== 5. 브레이크패드 테스트 ====================

    @Nested
    @DisplayName("브레이크패드 마모 계수 (Brake Pad Factor)")
    class BrakePadFactorTests {

        @Test
        @DisplayName("시내 주행: brake=5, avgSpeed=25 → city_mult=1.3")
        void testBrakePadCityDriving() {
            // brake_energy = 5 * 25^2 / 10000 = 5 * 625 / 10000 = 0.3125
            // city_mult = 1.3 (avgSpeed < 30)
            // factor = (1.0 + 0.3125) * 1.3 = 1.70625
            TripSummary trip = createTripWithBrakeSpeed(5, 25.0);
            Double factor = invokeCalculateBrakePadFactor(trip);
            assertEquals(1.70625, factor, 0.001);
        }

        @Test
        @DisplayName("고속 주행: brake=3, avgSpeed=80 → city_mult=1.0")
        void testBrakePadHighwayDriving() {
            // brake_energy = 3 * 80^2 / 10000 = 3 * 6400 / 10000 = 1.92
            // city_mult = 1.0 (avgSpeed >= 30)
            // factor = (1.0 + 1.92) * 1.0 = 2.92
            TripSummary trip = createTripWithBrakeSpeed(3, 80.0);
            Double factor = invokeCalculateBrakePadFactor(trip);
            assertEquals(2.92, factor, 0.001);
        }

        @Test
        @DisplayName("급제동 없음: brake=0 → factor=city_mult만 적용")
        void testBrakePadNoBraking() {
            // brake_energy = 0, city_mult = 1.3 (avgSpeed=20 < 30)
            // factor = (1.0 + 0) * 1.3 = 1.3
            TripSummary trip = createTripWithBrakeSpeed(0, 20.0);
            Double factor = invokeCalculateBrakePadFactor(trip);
            assertEquals(1.3, factor, 0.001);
        }

        @Test
        @DisplayName("Null 처리: avgSpeed=null → factor=1.0 (주행거리만 반영)")
        void testBrakePadNullValues() {
            TripSummary trip = TripSummary.builder().build();
            Double factor = invokeCalculateBrakePadFactor(trip);
            assertEquals(1.0, factor, 0.001);
        }

        @Test
        @DisplayName("극단 급제동: brake=1000, avgSpeed=100 → 상한(4.0) 적용, 유한값 반환")
        void testBrakePadExtremeValues() {
            // brake_energy = 1000 * 100^2 / 10000 = 1000 → raw factor 1001.0
            // BRAKE_PAD_MAX_FACTOR(4.0) 적용 → 4.0 반환
            TripSummary trip = createTripWithBrakeSpeed(1000, 100.0);
            Double factor = invokeCalculateBrakePadFactor(trip);
            assertNotNull(factor);
            assertFalse(factor.isInfinite(), "Factor should not be Infinity");
            assertFalse(factor.isNaN(), "Factor should not be NaN");
            assertEquals(4.0, factor, 0.001);
        }
    }

    // ==================== 헬퍼: Reflection 호출 ====================

    private Double invokeCalculateTireFactor(TripSummary trip) {
        return ReflectionTestUtils.invokeMethod(wearFactorService, "calculateTireFactor", trip);
    }

    private Double invokeCalculateEngineOilFactor(TripSummary trip, Double highRpmRatio, Double idleRatio) {
        return ReflectionTestUtils.invokeMethod(wearFactorService, "calculateEngineOilFactor",
                trip, highRpmRatio, idleRatio);
    }

    private Double invokeCalculateCoolantFactor(TripSummary trip) {
        return ReflectionTestUtils.invokeMethod(wearFactorService, "calculateCoolantFactor", trip);
    }

    private Double invokeCalculateAirFilterFactor(TripSummary trip, Vehicle vehicle) {
        return ReflectionTestUtils.invokeMethod(wearFactorService, "calculateAirFilterFactor", trip, vehicle);
    }

    private Double invokeCalculateBrakePadFactor(TripSummary trip) {
        return ReflectionTestUtils.invokeMethod(wearFactorService, "calculateBrakePadFactor", trip);
    }

    private Double invokeCalculateIdleRatio(TripSummary trip) {
        return ReflectionTestUtils.invokeMethod(wearFactorService, "calculateIdleRatio", trip);
    }

    // ==================== 헬퍼: 테스트 데이터 생성 ====================

    private TripSummary createTripWithAccelBrake(int accel, int brake) {
        TripSummary trip = TripSummary.builder().build();
        trip.setHardAccelCount(accel);
        trip.setHardBrakeCount(brake);
        return trip;
    }

    private TripSummary createTripWithDistance(double distance) {
        TripSummary trip = TripSummary.builder().build();
        trip.setDistance(distance);
        trip.setAvgRpm(2000.0); // RPM 있음 → 공식 적용 (미지원이면 1.0 반환하므로 테스트용 필수)
        trip.setHighRpmRatio(0.0);
        return trip;
    }

    private TripSummary createTripWithMaxCoolantTemp(double temp) {
        TripSummary trip = TripSummary.builder().build();
        trip.setMaxCoolantTemp(temp);
        return trip;
    }

    private TripSummary createTripWithMafThrottle(Double maf, Double throttle) {
        TripSummary trip = TripSummary.builder().build();
        trip.setAvgMaf(maf);
        trip.setAvgThrottlePos(throttle);
        return trip;
    }

    private TripSummary createTripWithBrakeSpeed(int brake, double speed) {
        TripSummary trip = TripSummary.builder().build();
        trip.setHardBrakeCount(brake);
        trip.setAverageSpeed(speed);
        return trip;
    }

    private TripSummary createTripWithIdleAndDuration(int idleTimeSec, int durationSec) {
        LocalDateTime start = LocalDateTime.of(2026, 1, 1, 12, 0, 0);
        LocalDateTime end = start.plusSeconds(durationSec);
        TripSummary trip = TripSummary.builder()
                .startTime(start)
                .endTime(end)
                .idleTime(idleTimeSec)
                .build();
        return trip;
    }

    private Vehicle createVehicleWithModel(String modelName) {
        return Vehicle.builder()
                .modelNameKo(modelName)
                .build();
    }
}
