package kr.co.himedia.repository;

import kr.co.himedia.entity.UserSetting;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface UserSettingRepository extends JpaRepository<UserSetting, UUID> {
}
