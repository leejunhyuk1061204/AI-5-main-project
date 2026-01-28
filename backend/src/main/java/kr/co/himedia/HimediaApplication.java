package kr.co.himedia;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.retry.annotation.EnableRetry;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableRetry
@EnableScheduling
@org.springframework.scheduling.annotation.EnableAsync
public class HimediaApplication {

	public static void main(String[] args) {
		// .env 파일 위치를 명시적으로 설정 (루트 디렉토리) - 더 강건한 경로 처리
		if (System.getProperty("dotenv.location") == null) {
			try {
				String rootPath = new java.io.File("..").getCanonicalPath();
				System.setProperty("dotenv.location", rootPath);
			} catch (java.io.IOException e) {
				System.setProperty("dotenv.location", "../");
			}
		}
		SpringApplication.run(HimediaApplication.class, args);
	}

}
