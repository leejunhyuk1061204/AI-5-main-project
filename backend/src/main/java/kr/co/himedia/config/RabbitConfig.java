package kr.co.himedia.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Qualifier;

@Configuration
public class RabbitConfig {

    public static final String EXCHANGE_NAME = "car-sentry.exchange";
    public static final String QUEUE_NAME = "ai.diagnosis.queue";
    public static final String ROUTING_KEY = "ai.diagnosis.unified";
    public static final String DLX_NAME = "ai.diagnosis.dlx";
    public static final String DLQ_NAME = "ai.diagnosis.dlq";

    // Cloud Sync 전용 설정
    public static final String CLOUD_SYNC_QUEUE = "cloud.vehicle.sync.queue";
    public static final String CLOUD_SYNC_DELAY_QUEUE = "cloud.vehicle.sync.delay.queue";
    public static final String CLOUD_SYNC_ROUTING_KEY = "cloud.vehicle.sync.request";

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
    public Binding aiDiagnosisDlBinding(@Qualifier("aiDiagnosisDlq") Queue aiDiagnosisDlq,
            @Qualifier("aiDiagnosisDlExchange") TopicExchange aiDiagnosisDlExchange) {
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
    public Binding aiDiagnosisBinding(@Qualifier("aiDiagnosisQueue") Queue aiDiagnosisQueue,
            @Qualifier("carSentryExchange") TopicExchange carSentryExchange) {
        return BindingBuilder.bind(aiDiagnosisQueue)
                .to(carSentryExchange)
                .with(ROUTING_KEY);
    }

    // --- Cloud Sync 전용 Bean 설정 ---

    @Bean
    public Queue cloudSyncQueue() {
        return new Queue(CLOUD_SYNC_QUEUE, true);
    }

    /**
     * 15초 지연 큐 설정 (TTL 15s)
     * 메시지가 TTL 만료 시 다시 메인 익스체인지의 메인 큐로 전송됨
     */
    @Bean
    public Queue cloudSyncDelayQueue() {
        return QueueBuilder.durable(CLOUD_SYNC_DELAY_QUEUE)
                .withArgument("x-message-ttl", 15000) // 15초 지연
                .withArgument("x-dead-letter-exchange", EXCHANGE_NAME)
                .withArgument("x-dead-letter-routing-key", CLOUD_SYNC_ROUTING_KEY)
                .build();
    }

    @Bean
    public Binding cloudSyncBinding(@Qualifier("cloudSyncQueue") Queue cloudSyncQueue,
            @Qualifier("carSentryExchange") TopicExchange carSentryExchange) {
        return BindingBuilder.bind(cloudSyncQueue)
                .to(carSentryExchange)
                .with(CLOUD_SYNC_ROUTING_KEY);
    }
}
