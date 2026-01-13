package kr.co.himedia.carsentry.domain.vehicle.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import kr.co.himedia.carsentry.domain.vehicle.dto.VehicleDto;
import kr.co.himedia.carsentry.domain.vehicle.entity.FuelType;
import kr.co.himedia.carsentry.domain.vehicle.service.VehicleService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Collections;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(VehicleController.class)
class VehicleControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private VehicleService vehicleService;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("차량 등록 성공 테스트")
    void registerVehicle_Success() throws Exception {
        // Given
        UUID userId = UUID.randomUUID();
        VehicleDto.RegistrationRequest request = new VehicleDto.RegistrationRequest();
        request.setManufacturer("Hyundai");
        request.setModelName("Sonata");
        request.setModelYear(2023);
        request.setFuelType(FuelType.GASOLINE);
        request.setTotalMileage(10000.0);

        VehicleDto.Response response = new VehicleDto.Response();
        response.setVehicleId(UUID.randomUUID());
        response.setUserId(userId);
        response.setManufacturer("Hyundai");
        response.setModelName("Sonata");

        given(vehicleService.registerVehicle(eq(userId), any(VehicleDto.RegistrationRequest.class)))
                .willReturn(response);

        // When & Then
        mockMvc.perform(post("/api/vehicles")
                .header("X-User-Id", userId.toString())
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.manufacturer").value("Hyundai"))
                .andExpect(jsonPath("$.modelName").value("Sonata"));
    }

    @Test
    @DisplayName("차량 목록 조회 테스트")
    void getVehicleList_Success() throws Exception {
        // Given
        UUID userId = UUID.randomUUID();
        VehicleDto.Response response = new VehicleDto.Response();
        response.setVehicleId(UUID.randomUUID());
        response.setManufacturer("Kia");

        given(vehicleService.getVehicleList(userId))
                .willReturn(Collections.singletonList(response));

        // When & Then
        mockMvc.perform(get("/api/vehicles")
                .header("X-User-Id", userId.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].manufacturer").value("Kia"));
    }

    @Test
    @DisplayName("차량 상세 조회 테스트")
    void getVehicleDetail_Success() throws Exception {
        // Given
        UUID vehicleId = UUID.randomUUID();
        VehicleDto.Response response = new VehicleDto.Response();
        response.setVehicleId(vehicleId);
        response.setManufacturer("Tesla");

        given(vehicleService.getVehicleDetail(vehicleId))
                .willReturn(response);

        // When & Then
        mockMvc.perform(get("/api/vehicles/{vehicleId}", vehicleId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.manufacturer").value("Tesla"));
    }

    @Test
    @DisplayName("차량 정보 수정 테스트")
    void updateVehicle_Success() throws Exception {
        // Given
        UUID vehicleId = UUID.randomUUID();
        VehicleDto.UpdateRequest request = new VehicleDto.UpdateRequest();
        request.setNickname("My Car");

        VehicleDto.Response response = new VehicleDto.Response();
        response.setVehicleId(vehicleId);
        response.setNickname("My Car");

        given(vehicleService.updateVehicle(eq(vehicleId), any(VehicleDto.UpdateRequest.class)))
                .willReturn(response);

        // When & Then
        mockMvc.perform(put("/api/vehicles/{vehicleId}", vehicleId)
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.nickname").value("My Car"));
    }

    @Test
    @DisplayName("대표 차량 설정 테스트")
    void setPrimaryVehicle_Success() throws Exception {
        // Given
        UUID userId = UUID.randomUUID();
        UUID vehicleId = UUID.randomUUID();

        // When & Then
        mockMvc.perform(patch("/api/vehicles/{vehicleId}/primary", vehicleId)
                .header("X-User-Id", userId.toString()))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("차량 삭제 테스트")
    void deleteVehicle_Success() throws Exception {
        // Given
        UUID vehicleId = UUID.randomUUID();

        // When & Then
        mockMvc.perform(delete("/api/vehicles/{vehicleId}", vehicleId))
                .andExpect(status().isNoContent());
    }
}
