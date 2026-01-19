package kr.co.himedia.repository;

import kr.co.himedia.entity.Notification;
import kr.co.himedia.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface NotificationRepository extends JpaRepository<Notification, Long> {
    List<Notification> findByUserOrderByCreatedAtDesc(User user);

    Long countByUserAndIsReadFalse(User user);
}
