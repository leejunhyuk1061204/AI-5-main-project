package kr.co.himedia.repository;

import kr.co.himedia.entity.ConsumableItem;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface ConsumableItemRepository extends JpaRepository<ConsumableItem, Long> {
    Optional<ConsumableItem> findByCode(String code);
}
