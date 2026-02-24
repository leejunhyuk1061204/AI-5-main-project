package kr.co.himedia.service;

import kr.co.himedia.entity.ConsumableItem;
import kr.co.himedia.entity.TripSummary;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.ConsumableItemRepository;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * WearFactorService 통합 테스트 (Mock 기반)
 *
 * calculateWearFactorsLocal() 메서드의 전체 실행 흐름을 검증합니다.
 * 실제 DB 대신 Mock을 사용하여 서비스 레이어 로직만 테스트합니다.
 */
@ExtendWith(MockitoExtension.class)
class WearFactorIntegrationTest {

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

    private Vehicle testVehicle;
    private UUID vehicleId;

    @BeforeEach
    void setUp() {
        vehicleId = UUID.randomUUID();
        testVehicle = Vehicle.builder()
                .totalMileage(50000.0)
                .modelNameKo("Sonata 2.0")
                .build();
        ReflectionTestUtils.setField(testVehicle, "vehicleId", vehicleId);
    }

    // ==================== 1. Null 필드 안전성 테스트 ====================

    @Test
    @DisplayName("모든 TripSummary 필드가 null → 예외 없이 실행 완료")
    void testNullFieldsSafety() {
        // Given: 최소한의 필드만 설정된 TripSummary
        TripSummary trip = TripSummary.builder()
                .vehicleId(vehicleId)
                .startTime(LocalDateTime.of(2026, 1, 1, 12, 0))
                .endTime(LocalDateTime.of(2026, 1, 1, 13, 0))
                .distance(10.0)
                .build();
        // 나머지 필드: null (hardAccelCount, hardBrakeCount, maxCoolantTemp, avgMaf, etc.)

        List<VehicleConsumable> consumables = createAllConsumables();

        when(vehicleRepository.findById(vehicleId)).thenReturn(Optional.of(testVehicle));
        when(vehicleConsumableRepository.findByVehicle(testVehicle)).thenReturn(consumables);

        // When & Then: 예외 없이 실행
        assertDoesNotThrow(() -> wearFactorService.calculateWearFactorsLocal(trip));

        // 5개 소모품 모두 저장되었는지 확인
        verify(vehicleConsumableRepository, times(5)).save(any(VehicleConsumable.class));
    }

    // ==================== 2. 전체 실행 흐름 테스트 ====================

    @Test
    @DisplayName("정상 주행 데이터 → 5개 소모품 마모 계수 모두 계산")
    void testFullExecutionFlow() {
        // Given: 정상적인 주행 데이터
        TripSummary trip = TripSummary.builder()
                .vehicleId(vehicleId)
                .startTime(LocalDateTime.of(2026, 1, 1, 12, 0))
                .endTime(LocalDateTime.of(2026, 1, 1, 13, 0))
                .distance(30.0)
                .hardAccelCount(5)
                .hardBrakeCount(3)
                .maxCoolantTemp(85.0)
                .avgMaf(16.0)
                .avgThrottlePos(50.0)
                .averageSpeed(40.0)
                .highRpmRatio(0.1)
                .idleTime(120)
                .build();

        List<VehicleConsumable> consumables = createAllConsumables();

        when(vehicleRepository.findById(vehicleId)).thenReturn(Optional.of(testVehicle));
        when(vehicleConsumableRepository.findByVehicle(testVehicle)).thenReturn(consumables);

        // When
        assertDoesNotThrow(() -> wearFactorService.calculateWearFactorsLocal(trip));

        // Then: 모든 소모품의 wearFactor가 설정됨
        for (VehicleConsumable vc : consumables) {
            assertNotNull(vc.getWearFactor(), vc.getConsumableItem().getCode() + " factor should not be null");
            assertTrue(vc.getWearFactor() >= 1.0, vc.getConsumableItem().getCode() + " factor should be >= 1.0");
            assertFalse(vc.getWearFactor().isInfinite(),
                    vc.getConsumableItem().getCode() + " factor should not be Infinite");
            assertFalse(vc.getWearFactor().isNaN(), vc.getConsumableItem().getCode() + " factor should not be NaN");
        }

        verify(vehicleConsumableRepository, times(5)).save(any(VehicleConsumable.class));
    }

    // ==================== 3. 공격적 주행 테스트 ====================

    @Test
    @DisplayName("공격적 주행 → 마모 계수가 정상 주행보다 높음")
    void testAggressiveDriving() {
        // Given: 공격적 주행 데이터
        TripSummary aggressiveTrip = TripSummary.builder()
                .vehicleId(vehicleId)
                .startTime(LocalDateTime.of(2026, 1, 1, 12, 0))
                .endTime(LocalDateTime.of(2026, 1, 1, 12, 30))
                .distance(3.0) // 짧은 거리 (cold start)
                .avgRpm(3500.0) // RPM 있음 → 엔진오일/스파크플러그 공식 적용
                .avgEngineLoad(75.0)
                .hardAccelCount(20)
                .hardBrakeCount(15)
                .maxCoolantTemp(105.0) // 과열
                .maxEngineLoad(90.0)
                .avgMaf(10.0) // 낮은 MAF (에어필터 열화)
                .avgThrottlePos(80.0)
                .averageSpeed(20.0) // 시내 주행
                .highRpmRatio(0.6) // 높은 RPM 비율
                .idleTime(300) // 긴 공회전
                .build();

        List<VehicleConsumable> aggressiveConsumables = createAllConsumables();

        when(vehicleRepository.findById(vehicleId)).thenReturn(Optional.of(testVehicle));
        when(vehicleConsumableRepository.findByVehicle(testVehicle)).thenReturn(aggressiveConsumables);

        // When
        assertDoesNotThrow(() -> wearFactorService.calculateWearFactorsLocal(aggressiveTrip));

        // Then: 공격적 주행의 마모 계수가 높음을 확인
        for (VehicleConsumable vc : aggressiveConsumables) {
            String code = vc.getConsumableItem().getCode();
            Double factor = vc.getWearFactor();
            assertNotNull(factor, code + " factor should not be null");

            // 공격적 주행에서는 모든 factor가 1.0보다 커야 함
            assertTrue(factor > 1.0, code + " factor should be > 1.0 for aggressive driving, got: " + factor);
        }
    }

    // ==================== 헬퍼: 5개 소모품 생성 ====================

    private List<VehicleConsumable> createAllConsumables() {
        // 실제 도메인 코드 및 시드 데이터(db/seed_consumable.sql)에 맞춘 5개 대표 소모품
        return List.of(
                createConsumable("TIRE_FL", "앞왼쪽 타이어", 50000),     // 타이어 (대표 1개)
                createConsumable("ENGINE_OIL", "엔진 오일", 10000),
                createConsumable("COOLANT", "냉각수", 40000),
                createConsumable("AIR_FILTER", "에어필터", 15000),
                createConsumable("BRAKE_PAD_FRONT", "앞 브레이크 패드", 30000)); // 브레이크 패드 (대표 1개)
    }

    private VehicleConsumable createConsumable(String code, String name, int intervalMileage) {
        ConsumableItem item = new ConsumableItem();
        item.setCode(code);
        item.setName(name);
        item.setDefaultIntervalMileage(intervalMileage);

        VehicleConsumable vc = new VehicleConsumable();
        vc.setId(UUID.randomUUID());
        vc.setVehicle(testVehicle);
        vc.setConsumableItem(item);
        vc.setWearFactor(1.0);
        vc.setRemainingLife(80.0);
        vc.setLastReplacedMileage(40000.0);
        return vc;
    }
}
