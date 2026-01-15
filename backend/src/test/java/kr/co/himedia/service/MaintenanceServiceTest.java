package kr.co.himedia.service;

import kr.co.himedia.dto.maintenance.ConsumableStatusResponse;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryRequest;
import kr.co.himedia.dto.maintenance.MaintenanceHistoryResponse;
import kr.co.himedia.entity.MaintenanceHistory;
import kr.co.himedia.entity.MaintenanceItem;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.entity.VehicleConsumable;
import kr.co.himedia.repository.MaintenanceHistoryRepository;
import kr.co.himedia.repository.VehicleConsumableRepository;
import kr.co.himedia.repository.VehicleRepository;
import kr.co.himedia.service.ai.AiClient;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class MaintenanceServiceTest {

    @Mock
    private MaintenanceHistoryRepository maintenanceHistoryRepository;
    @Mock
    private VehicleConsumableRepository vehicleConsumableRepository;
    @Mock
    private VehicleRepository vehicleRepository;
    @Mock
    private AiClient aiClient;

    @InjectMocks
    private MaintenanceService maintenanceService;

    @Test
    @DisplayName("정비 이력 등록 시 차량 소모품 정보가 존재하면 업데이트한다.")
    void registerMaintenance_shouldUpdateExistingConsumable() {
        // given
        UUID vehicleId = UUID.randomUUID();
        Vehicle vehicle = Vehicle.builder().userId(UUID.randomUUID()).build();

        MaintenanceHistoryRequest request = new MaintenanceHistoryRequest();
        request.setMaintenanceDate(LocalDate.now());
        request.setMileageAtMaintenance(50000.0);
        request.setItem(MaintenanceItem.ENGINE_OIL);
        request.setCost(80000);
        request.setMemo("엔진오일 교체");

        VehicleConsumable existingConsumable = VehicleConsumable.builder()
                .vehicle(vehicle)
                .item(MaintenanceItem.ENGINE_OIL)
                .lastMaintenanceMileage(40000.0)
                .lastMaintenanceDate(LocalDate.now().minusMonths(6))
                .build();

        given(vehicleRepository.findById(vehicleId)).willReturn(Optional.of(vehicle));
        given(vehicleConsumableRepository.findByVehicleAndItem(any(), any()))
                .willReturn(Optional.of(existingConsumable));
        given(maintenanceHistoryRepository.save(any())).willAnswer(invocation -> invocation.getArgument(0));

        // when
        MaintenanceHistoryResponse response = maintenanceService.registerMaintenance(vehicleId, request);

        // then
        assertThat(response.getItem()).isEqualTo(MaintenanceItem.ENGINE_OIL);
        assertThat(existingConsumable.getLastMaintenanceMileage()).isEqualTo(50000.0);
        verify(maintenanceHistoryRepository, times(1)).save(any());
        verify(vehicleConsumableRepository, times(1)).findByVehicleAndItem(any(), any());
    }

    @Test
    @DisplayName("정비 이력 등록 시 차량 소모품 정보가 없으면 새로 생성한다.")
    void registerMaintenance_shouldCreateNewConsumable() {
        // given
        UUID vehicleId = UUID.randomUUID();
        Vehicle vehicle = Vehicle.builder().userId(UUID.randomUUID()).build();

        MaintenanceHistoryRequest request = new MaintenanceHistoryRequest();
        request.setMaintenanceDate(LocalDate.now());
        request.setMileageAtMaintenance(10000.0);
        request.setItem(MaintenanceItem.TIRE);

        given(vehicleRepository.findById(vehicleId)).willReturn(Optional.of(vehicle));
        given(vehicleConsumableRepository.findByVehicleAndItem(any(), any())).willReturn(Optional.empty());
        given(maintenanceHistoryRepository.save(any())).willAnswer(invocation -> invocation.getArgument(0));

        // when
        maintenanceService.registerMaintenance(vehicleId, request);

        // then
        verify(vehicleConsumableRepository, times(1)).save(any(VehicleConsumable.class));
    }

    @Test
    @DisplayName("차량의 소모품 잔존 수명을 조회한다.")
    void getConsumableStatus_shouldReturnStatusList() {
        // given
        UUID vehicleId = UUID.randomUUID();
        Vehicle vehicle = Vehicle.builder()
                .userId(UUID.randomUUID())
                .totalMileage(10000.0)
                .fuelType(kr.co.himedia.entity.FuelType.GASOLINE)
                .modelYear(2022)
                .build();

        VehicleConsumable consumable = VehicleConsumable.builder()
                .vehicle(vehicle)
                .item(MaintenanceItem.ENGINE_OIL)
                .lastMaintenanceMileage(5000.0)
                .lastMaintenanceDate(LocalDate.now().minusMonths(3))
                .replacementIntervalMileage(10000.0)
                .build();

        given(vehicleRepository.findById(vehicleId)).willReturn(Optional.of(vehicle));
        given(vehicleConsumableRepository.findByVehicle(vehicle)).willReturn(List.of(consumable));

        kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse aiResponse = new kr.co.himedia.dto.maintenance.ai.AiWearFactorResponse();
        aiResponse.setPredictedWearFactor(1.2);
        given(aiClient.getWearFactor(any())).willReturn(aiResponse);

        // when
        List<ConsumableStatusResponse> responses = maintenanceService.getConsumableStatus(vehicleId);

        // then
        assertThat(responses).hasSize(1);
        ConsumableStatusResponse res = responses.get(0);
        assertThat(res.getItem()).isEqualTo(MaintenanceItem.ENGINE_OIL);
        // 계산: (10000 - (10000 - 5000) * 1.2) / 10000 * 100 = 40.0%
        assertThat(res.getRemainingLifePercent()).isEqualTo(40.0);
    }
}
