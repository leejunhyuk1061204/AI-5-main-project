package kr.co.himedia.service;

import kr.co.himedia.common.util.EncryptionUtils;
import kr.co.himedia.dto.cloud.CloudVehicleRegisterRequest;
import kr.co.himedia.dto.cloud.CloudVehicleResponse;
import kr.co.himedia.dto.cloud.TokenExchangeResponse;
import kr.co.himedia.entity.CloudAccount;
import kr.co.himedia.entity.CloudConnectionStatus;
import kr.co.himedia.entity.CloudProvider;
import kr.co.himedia.entity.User;
import kr.co.himedia.entity.Vehicle;
import kr.co.himedia.repository.CloudAccountRepository;
import kr.co.himedia.repository.UserRepository;
import kr.co.himedia.repository.VehicleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class CloudAuthService {

    private final CloudAccountRepository cloudAccountRepository;
    private final UserRepository userRepository;
    private final VehicleRepository vehicleRepository;
    private final VehicleService vehicleService;
    private final EncryptionUtils encryptionUtils;

    /**
     * 클라우드 서비스에서 연동된 차량 목록을 조회합니다.
     */
    public List<CloudVehicleResponse> getConnectedVehicles(UUID userId, CloudProvider provider) {
        log.info("차량 목록 조회 시작 - userId: {}, provider: {}", userId, provider);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found: " + userId));

        CloudAccount account = cloudAccountRepository.findByUserAndProvider(user, provider)
                .orElseThrow(() -> new RuntimeException("연동된 클라우드 계정이 없습니다."));

        // 토큰 유효성 확인 및 필요시 갱신
        String accessToken = ensureValidToken(account, provider);

        if (provider == CloudProvider.HIGH_MOBILITY) {
            // TODO: High Mobility 차량 조회 구현 예정 (서비스 분리 고려)
            return Collections.emptyList();
        } else {
            throw new UnsupportedOperationException("지원하지 않는 서비스입니다.");
        }
    }

    /**
     * 사용자가 선택한 클라우드 차량을 우리 시스템에 등록합니다.
     */
    public Vehicle registerCloudVehicle(UUID userId, CloudVehicleRegisterRequest request) {
        log.info("차량 등록 시작 - userId: {}, providerVehicleId: {}", userId, request.getProviderVehicleId());

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new RuntimeException("User not found: " + userId));

        CloudAccount account = cloudAccountRepository.findByUserAndProvider(user, request.getCloudProvider())
                .orElseThrow(() -> new RuntimeException("연동된 클라우드 계정이 없습니다."));

        // TODO: 차량 정보 조회 및 등록 로직 구현 (High Mobility 전용 서비스 개발 예정)
        throw new UnsupportedOperationException("차량 등록 로직은 현재 준비 중입니다.");
    }

    /**
     * 인가 코드를 받아 토큰을 교환하고 저장합니다.
     * (High Mobility는 Client Credentials Flow를 사용할 예정이므로 이 메서드는 추후 재설계될 수 있음)
     */
    public void exchangeCodeAndSave(UUID userId, String code, CloudProvider provider) {
        if (provider != CloudProvider.HIGH_MOBILITY) {
            throw new UnsupportedOperationException("현재 High Mobility 연동만 준비 중입니다.");
        }

        // TODO: High Mobility 토큰 교환 로직 구현 예정
        log.warn("High Mobility 토큰 교환 로직이 아직 구현되지 않았습니다.");
    }

    /**
     * 토큰 유효성을 확인하고 필요 시 갱신합니다.
     */
    private String ensureValidToken(CloudAccount account, CloudProvider provider) {
        // TODO: 토큰 만료 체크 및 갱신 로직 구현
        return encryptionUtils.decrypt(account.getAccessToken());
    }

    /**
     * 차량의 VIN 정보를 기록합니다.
     */
    public void updateVehicleVin(UUID vehicleId, String plainVin) {
        vehicleService.updateVehicleVin(vehicleId, plainVin);
    }
}
