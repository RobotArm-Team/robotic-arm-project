package com.robotarm.management.service;

import com.robotarm.management.domain.SystemStatus;
import com.robotarm.management.repository.SystemStatusRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;

/**
 * 系统状态读写；system_status 表固定只有一行（id = 1）。
 */
@Service
public class SystemStatusService {

    private static final long STATUS_ID = 1L;

    private final SystemStatusRepository repository;

    public SystemStatusService(SystemStatusRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public SystemStatus current() {
        return repository.findById(STATUS_ID).orElseGet(this::createDefault);
    }

    @Transactional
    public SystemStatus update(String status, String armState, Instant updatedAt) {
        SystemStatus current = current();
        current.setStatus(status);
        current.setArmState(armState);
        current.setUpdatedAt(updatedAt);
        return repository.save(current);
    }

    private SystemStatus createDefault() {
        return repository.save(new SystemStatus(STATUS_ID, "READY", "IDLE", false, true, Instant.now()));
    }
}
