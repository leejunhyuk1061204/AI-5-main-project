package kr.co.himedia.global.config;

import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitConfig {

    /**
     * RabbitMQ 메시지를 JSON으로 직렬화/역직렬화하기 위한 설정
     * Python(AI) 등 다른 언어와 통신 시 필수
     */
    @Bean
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
