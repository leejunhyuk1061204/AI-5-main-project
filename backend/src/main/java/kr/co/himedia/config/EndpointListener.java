package kr.co.himedia.config;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerMapping;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class EndpointListener implements ApplicationListener<ApplicationReadyEvent> {

    private final RequestMappingHandlerMapping requestMappingHandlerMapping;

    @Override
    public void onApplicationEvent(ApplicationReadyEvent event) {
        log.info("=================================================");
        log.info("Registered Endpoints:");
        requestMappingHandlerMapping.getHandlerMethods().forEach((key, value) -> {
            log.info("URL: {}", key);
        });
        log.info("=================================================");
    }
}
