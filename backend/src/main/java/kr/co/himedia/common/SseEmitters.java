package kr.co.himedia.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Slf4j
public class SseEmitters {

    private final Map<String, SseEmitter> emitters = new ConcurrentHashMap<>();

    public SseEmitter add(String sessionId) {
        // 5분 타임아웃 설정 (진단이 길어질 수 있음)
        SseEmitter emitter = new SseEmitter(5 * 60 * 1000L);
        this.emitters.put(sessionId, emitter);

        log.info("SSE Emitter added: {}", sessionId);

        try {
            emitter.send(SseEmitter.event().name("open").data("connected"));
        } catch (IOException e) {
            log.warn("Failed to send initial SSE open event to {}", sessionId, e);
        }

        emitter.onCompletion(() -> {
            log.info("SSE Emitter completed: {}", sessionId);
            this.emitters.remove(sessionId);
        });
        emitter.onTimeout(() -> {
            log.info("SSE Emitter timeout: {}", sessionId);
            emitter.complete();
            this.emitters.remove(sessionId);
        });
        emitter.onError((e) -> {
            log.error("SSE Emitter error: {}", sessionId, e);
            emitter.complete();
            this.emitters.remove(sessionId);
        });

        return emitter;
    }

    public void send(String sessionId, String name, Object data) {
        SseEmitter emitter = this.emitters.get(sessionId);
        if (emitter != null) {
            try {
                emitter.send(SseEmitter.event()
                        .name(name)
                        .data(data));
                log.info("SSE Notification sent to {}: {} -> {}", sessionId, name, data);
            } catch (IOException e) {
                log.error("Failed to send SSE event to {}", sessionId, e);
                this.emitters.remove(sessionId);
            }
        } else {
            log.warn("No active SSE Emitter found for sessionId: {}", sessionId);
        }
    }
}
