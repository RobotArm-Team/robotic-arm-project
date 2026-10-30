package com.robotarm.management.repository;

import com.robotarm.management.domain.ExceptionEvent;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ExceptionEventRepository extends JpaRepository<ExceptionEvent, String> {
}
