package kr.co.himedia.config;

import com.google.auth.oauth2.GoogleCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Slf4j
@Configuration
public class FirebaseConfig {

    @Value("${app.firebase.config-path}")
    private String firebaseConfigPath;

    @PostConstruct
    public void initialize() {
        try {
            if (FirebaseApp.getApps().isEmpty()) {
                InputStream serviceAccountStream = null;

                // 1. Try ClassPath (Standard Spring Boot)
                try {
                    org.springframework.core.io.ClassPathResource resource = new org.springframework.core.io.ClassPathResource(
                            firebaseConfigPath);
                    if (resource.exists()) {
                        serviceAccountStream = resource.getInputStream();
                        log.info("Loaded Firebase config from ClassPath: {}", firebaseConfigPath);
                    }
                } catch (Exception e) {
                    log.warn("Failed to load from ClassPath: {}", e.getMessage());
                }

                // 2. Try filesystem (src/main/resources - Local Dev)
                if (serviceAccountStream == null) {
                    try {
                        Path path = Paths.get("src/main/resources", firebaseConfigPath);
                        if (Files.exists(path)) {
                            serviceAccountStream = Files.newInputStream(path);
                            log.info("Loaded Firebase config from filesystem (dev): {}", path);
                        }
                    } catch (Exception e) {
                        log.warn("Failed to load from filesystem (dev): {}", e.getMessage());
                    }
                }

                // 3. Try filesystem (Root - Fallback)
                if (serviceAccountStream == null) {
                    try {
                        Path path = Paths.get(firebaseConfigPath);
                        if (Files.exists(path)) {
                            serviceAccountStream = Files.newInputStream(path);
                            log.info("Loaded Firebase config from filesystem (root): {}", path);
                        }
                    } catch (Exception e) {
                        log.warn("Failed to load from filesystem (root): {}", e.getMessage());
                    }
                }

                if (serviceAccountStream == null) {
                    log.error(
                            "Firebase config file not found. Checked ClassPath, src/main/resources, and root. Path: {}",
                            firebaseConfigPath);
                    return;
                }

                FirebaseOptions options = FirebaseOptions.builder()
                        .setCredentials(GoogleCredentials.fromStream(serviceAccountStream))
                        .build();

                FirebaseApp.initializeApp(options);
                log.info("Firebase application has been initialized");
            }
        } catch (IOException e) {
            log.error("Failed to initialize Firebase: {}", e.getMessage());
        }
    }
}
