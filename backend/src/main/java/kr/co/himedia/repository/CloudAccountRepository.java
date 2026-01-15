package kr.co.himedia.repository;

import kr.co.himedia.entity.CloudAccount;
import kr.co.himedia.entity.CloudProvider;
import kr.co.himedia.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface CloudAccountRepository extends JpaRepository<CloudAccount, UUID> {
    Optional<CloudAccount> findByUserAndProvider(User user, CloudProvider provider);
}
