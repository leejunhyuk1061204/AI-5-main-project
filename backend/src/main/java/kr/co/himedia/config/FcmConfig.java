package kr.co.himedia.config;

import com.google.auth.oauth2.GoogleCredentials;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import javax.annotation.PostConstruct;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.Collections;

@Configuration
public class FcmConfig {

    @Value("${firebase.config.path:firebase-service-account.json}")
    private String firebaseConfigPath;

    @PostConstruct
    public void init() {
        try {
            // 이미 초기화된 경우 건너뜀
            if (!FirebaseApp.getApps().isEmpty()) {
                return;
            }

            FileInputStream serviceAccount = new FileInputStream(firebaseConfigPath);

            FirebaseOptions options = FirebaseOptions.builder()
                    .setCredentials(GoogleCredentials.fromStream(serviceAccount))
                    .build();

            FirebaseApp.initializeApp(options);
            System.out.println("FCM Initialized successfully.");

        } catch (IOException e) {
            System.err.println("FCM Initialization failed: " + e.getMessage());
            // 개발 환경에서 키 파일이 없을 수 있으므로 애플리케이션 시작을 막지는 않음
        }
    }
}
