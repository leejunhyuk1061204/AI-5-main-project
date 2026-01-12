package kr.co.himedia.backend.global.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;

@Configuration
public class UserConfig {

    /**
     * 임시 사용자 설정 (순환 참조 방지용)
     * SecurityConfig -> JwtTokenProvider -> UserDetailsService -> SecurityConfig 순환
     * 참조를 끊기 위해 별도 Config로 분리
     */
    @Bean
    public UserDetailsService userDetailsService() {
        UserDetails user = User.builder()
                .username("user")
                .password("{noop}password") // 테스트용이므로 암호화 없이 설정 ({noop} 접두사 사용)
                .roles("USER")
                .build();
        return new InMemoryUserDetailsManager(user);
    }
}
