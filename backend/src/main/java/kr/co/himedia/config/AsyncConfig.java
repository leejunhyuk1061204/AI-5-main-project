package kr.co.himedia.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * 프로젝트의 비동기(@Async) 처리를 활성화하기 위한 설정 클래스입니다.
 */
@Configuration
@EnableAsync
public class AsyncConfig {
}
