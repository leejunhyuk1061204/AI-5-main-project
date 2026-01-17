# API 통합 테스트 가이드 (Insomnia 전용)

이 문서는 모든 API 기능을 깨끗한 환경에서 처음부터 끝까지 점검하기 위한 가이드입니다. 
HAR 파일 임포트로 인한 데이터 꼬임을 방지하기 위해, 가급적 Insomnia에서 **[New Request]**를 눌러 새로 만들어 진행해 주세요.

---

## 🚀 1단계: 로그인 (토큰 발급)
가장 먼저 수행해야 하며, 여기서 받은 `accessToken`을 이후 모든 요청에서 사용합니다.

*   **Method**: `POST`
*   **URL**: `http://localhost:8080/api/v1/auth/login`
*   **Body (JSON)**:
    ```json
    {
      "email": "tester33@test.com",
      "password": "password123!"
    }
    ```
*   **확인 사항**: 응답의 `data.accessToken` 값을 따옴표 없이 복사해 두세요.

---

## 🚗 2단계: 차량 등록
토큰 인증이 필수인 첫 번째 단계입니다.

*   **Method**: `POST`
*   **URL**: `http://localhost:8080/api/v1/vehicles`
*   **Auth**: `Bearer Token` 선택 -> 1단계에서 복사한 토큰 붙여넣기
*   **Body (JSON)**:
    ```json
    {
      "manufacturer": "HYUNDAI",
      "modelName": "AVANTE",
      "modelYear": 2024,
      "fuelType": "GASOLINE",
      "totalMileage": 5000.0,
      "carNumber": "123가4567",
      "nickname": "내 자동차",
      "memo": "가이드 테스트 차량"
    }
    ```

---

## 🛣️ 3단계: 주행 시작
차량이 등록된 후 주행을 시작하는 단계입니다.

*   **Method**: `POST`
*   **URL**: `http://localhost:8080/api/v1/trips/start`
*   **Auth**: `Bearer Token` (동일한 토큰 사용)
*   **Body (JSON)**:
    ```json
    {
      "vehicleId": 1, 
      "startLatitude": 37.5665,
      "startLongitude": 126.9780,
      "startLocationName": "서울시청"
    }
    ```

---

## 🏁 4단계: 주행 종료
주행을 마무리하고 데이터를 정산합니다.

*   **Method**: `POST`
*   **URL**: `http://localhost:8080/api/v1/trips/1/finish`
*   **Auth**: `Bearer Token`
*   **Body (JSON)**:
    ```json
    {
      "endLatitude": 37.4012,
      "endLongitude": 127.1086,
      "endLocationName": "판교역",
      "distance": 25.5,
      "fuelConsumed": 2.1
    }
    ```

---

## 💡 주의 사항
1.  **토큰 만료 시간**: 현재 테스트 편의를 위해 **24시간**으로 대폭 늘려두었습니다.
2.  **403 Forbidden 발생 시**: 인솜니아의 **[Auth]** 탭에 토큰이 최신 버전으로 들어있는지, 혹은 **[Headers]** 탭에 예전 `Authorization` 헤더가 남아있는지 확인해 주세요.
3.  **로그 확인**: `backend/logs/backend.log`를 통해 서버의 상세 처리 과정을 실시간으로 확인할 수 있습니다.
