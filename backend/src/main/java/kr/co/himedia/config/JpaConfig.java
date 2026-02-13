package kr.co.himedia.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

@Configuration
@EnableJpaAuditing
@EnableJpaRepositories(basePackages = "kr.co.himedia.repository")
public class JpaConfig {
}
