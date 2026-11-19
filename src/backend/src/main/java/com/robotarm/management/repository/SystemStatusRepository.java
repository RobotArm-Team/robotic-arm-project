package com.robotarm.management.repository;

import com.robotarm.management.domain.SystemStatus;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SystemStatusRepository extends JpaRepository<SystemStatus, Long> {
}
