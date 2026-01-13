## 구현 계획 (작업 목록)

1. DB Migration: `users` 테이블 생성
	- 파일: `src/main/resources/db/migration/V1__create_users.sql`
	- 컬럼: `user_id` (UUID PK), `email` VARCHAR(255) UNIQUE NOT NULL, `password_hash` VARCHAR(255), `nickname` VARCHAR(50), `created_at` TIMESTAMP DEFAULT NOW(), `deleted_at` TIMESTAMP NULL

2. JPA 엔티티 추가
	- 위치: `src/main/java/kr/co/himedia/backend/domain/user/User.java`
	- 타입: `UUID` 기반 `@Id` 필드, `email`에 `@Column(unique=true)`

3. Repository 및 DTO
	- `UserRepository` (Spring Data JPA)
	- DTOs: `SignupRequest(email,password,nickname)`, `UserResponse(userId,email,nickname)`

4. 서비스 구현 (비밀번호 암호화)
	- `UserService.createUser(SignupRequest)`
	- 이메일 중복 확인, `BCryptPasswordEncoder`로 패스워드 해시, 저장 후 `UserResponse` 반환

5. 컨트롤러: 회원가입 엔드포인트
	- `POST /api/v1/auth/signup`
	- 입력 검증(이메일 형식, 비밀번호 최소 길이 등), 에러 시 적절한 상태코드 반환

6. 설정 및 환경
	- `application.yml`에 PostgreSQL 연결 확인
	- 로컬 실행 시 `.env`의 DB 크레덴셜 사용(수동 설정 필요)

7. 테스트
	- `UserService` 단위 테스트
	- `AuthController` 기본 통합 테스트(가능하면 Testcontainers 사용)

8. 프론트 연동 스펙 (UI 변경 없음)
	- API: `POST /api/v1/auth/signup`
	- 요청 JSON: `{ "email": "", "password": "", "nickname": "" }`
	- 성공 응답: `201 Created` + `{ "userId": "<uuid>", "email": "", "nickname": "" }`
	- 에러: `400`(유효성 실패), `409`(이메일 중복)

파일에서 확인: [.agent/task.md](.agent/task.md)

	---

	## 업데이트된 구현 계획 (controller/service 구조 반영)

	목표: 프론트는 변경하지 않고, 백엔드에서 `users` 회원가입 기능을 `controller`/`service` 디렉터리 구조로 구현합니다.

	작업 단계 (우선순위 순)

	1) 마이그레이션
		- 경로: `src/main/resources/db/migration/V1__create_users.sql`
		- 내용: `CREATE TABLE users ( user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) UNIQUE NOT NULL, password_hash VARCHAR(255), nickname VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(), deleted_at TIMESTAMP );`

	2) 엔티티
		- 파일: `src/main/java/kr/co/himedia/backend/domain/user/User.java`
		- 필드: `UUID userId`, `String email`, `String passwordHash`, `String nickname`, `LocalDateTime createdAt`, `LocalDateTime deletedAt`

	3) 리포지토리
		- 파일: `src/main/java/kr/co/himedia/backend/repository/UserRepository.java`
		- 인터페이스: `Optional<User> findByEmail(String email);` 포함

	4) 서비스 (비즈니스 로직)
		- 파일: `src/main/java/kr/co/himedia/backend/service/auth/UserService.java`
		- 역할: 이메일 중복 검사, 비밀번호 `BCrypt` 해시, 사용자 저장, 예외/에러 변환

	5) 컨트롤러 (HTTP 엔드포인트)
		- 파일: `src/main/java/kr/co/himedia/backend/controller/auth/AuthController.java`
		- 엔드포인트: `POST /api/v1/auth/signup`
		- 요청 DTO: `SignupRequest { email, password, nickname }`
		- 응답: `201 Created` + `UserResponse { userId, email, nickname }`
		- 에러 처리: 유효성 실패 `400`, 이메일 중복 `409`, 서버 오류 `500`

	6) 유효성 규칙 (간단)
		- `email`: RFC-5322 기반 단순 체크(존재 및 '@')
		- `password`: 최소 8자, 추천 영문+숫자 조합
		- `nickname`: 1~50자

	7) 설정
		- `application.yml`에 `spring.datasource` 설정 확인
		- 로컬: `.env`의 DB 설정을 IntelliJ Run Configuration의 Environment variables로 전달하거나 수동 입력

	8) 테스트
		- `UserService` 단위 테스트 (중복 예외, 정상 생성)
		- `AuthController` 통합 테스트 (MockMvc 또는 Testcontainers)

	9) 프론트 연동 스펙 (변경 없음)
		- API: `POST /api/v1/auth/signup`
		- 요청: `{ "email": "", "password": "", "nickname": "" }`
		- 응답: `201` / `{ "userId": "<uuid>", "email": "", "nickname": "" }`

	추가 옵션: 바로 코드 생성(마이그레이션·엔티티·레포·서비스·컨트롤러)을 시작할까요?