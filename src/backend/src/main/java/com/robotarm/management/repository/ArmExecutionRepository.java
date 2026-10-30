package com.robotarm.management.repository;

import com.robotarm.management.domain.ArmExecution;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ArmExecutionRepository extends JpaRepository<ArmExecution, String> {
}
