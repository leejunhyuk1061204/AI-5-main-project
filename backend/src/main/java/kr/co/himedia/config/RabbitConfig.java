package kr.co.himedia.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitConfig {

    public static final String EXCHANGE_NAME = "car-sentry.exchange";
    public static final String QUEUE_NAME = "ai.diagnosis.queue";
    public static final String ROUTING_KEY = "ai.diagnosis.unified";
    public static final String DLX_NAME = "ai.diagnosis.dlx";
    public static final String DLQ_NAME = "ai.diagnosis.dlq";

    @Bean
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }

    @Bean
    public TopicExchange carSentryExchange() {
        return new TopicExchange(EXCHANGE_NAME);
    }

    @Bean
    public TopicExchange aiDiagnosisDlExchange() {
        return new TopicExchange(DLX_NAME);
    }

    @Bean
    public Queue aiDiagnosisDlq() {
        return new Queue(DLQ_NAME, true);
    }

    @Bean
    public Binding aiDiagnosisDlBinding(Queue aiDiagnosisDlq, TopicExchange aiDiagnosisDlExchange) {
        return BindingBuilder.bind(aiDiagnosisDlq)
                .to(aiDiagnosisDlExchange)
                .with("ai.diagnosis.dead");
    }

    @Bean
    public Queue aiDiagnosisQueue() {
        return QueueBuilder.durable(QUEUE_NAME)
                .withArgument("x-dead-letter-exchange", DLX_NAME)
                .withArgument("x-dead-letter-routing-key", "ai.diagnosis.dead")
                .build();
    }

    @Bean
    public Binding aiDiagnosisBinding(Queue aiDiagnosisQueue, TopicExchange carSentryExchange) {
        return BindingBuilder.bind(aiDiagnosisQueue)
                .to(carSentryExchange)
                .with(ROUTING_KEY);
    }
}
