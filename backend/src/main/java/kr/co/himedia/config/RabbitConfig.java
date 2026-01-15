package kr.co.himedia.config;

import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;

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

    // --- Exchange ---
    @Bean
    public TopicExchange carSentryExchange() {
        return new TopicExchange("car-sentry.exchange");
    }

    // --- Queue ---
    @Bean
    public Queue aiDiagnosisQueue() {
        return new Queue("ai.diagnosis.queue", true); // durable=true
    }

    // --- Binding ---
    @Bean
    public Binding aiDiagnosisBinding(Queue aiDiagnosisQueue, TopicExchange carSentryExchange) {
        return BindingBuilder.bind(aiDiagnosisQueue)
                .to(carSentryExchange)
                .with("ai.diagnosis.#"); // Routing Key Pattern
    }
}
