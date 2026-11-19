package com.robotarm.management.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.Instant;

/**
 * 系统状态，对应表 system_status；表中固定只有 id = 1 的一行。
 */
@Entity
@Table(name = "system_status")
public class SystemStatus {

    @Id
    @Column(name = "id", nullable = false)
    private Long id;

    @Column(name = "status", nullable = false, length = 32)
    private String status;

    @Column(name = "arm_state", nullable = false, length = 32)
    private String armState;

    @Column(name = "estop_active", nullable = false)
    private boolean estopActive;

    @Column(name = "fault_cleared", nullable = false)
    private boolean faultCleared;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected SystemStatus() {
    }

    public SystemStatus(Long id, String status, String armState, boolean estopActive, boolean faultCleared,
                        Instant updatedAt) {
        this.id = id;
        this.status = status;
        this.armState = armState;
        this.estopActive = estopActive;
        this.faultCleared = faultCleared;
        this.updatedAt = updatedAt;
    }

    public Long getId() {
        return id;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getArmState() {
        return armState;
    }

    public void setArmState(String armState) {
        this.armState = armState;
    }

    public boolean isEstopActive() {
        return estopActive;
    }

    public void setEstopActive(boolean estopActive) {
        this.estopActive = estopActive;
    }

    public boolean isFaultCleared() {
        return faultCleared;
    }

    public void setFaultCleared(boolean faultCleared) {
        this.faultCleared = faultCleared;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }
}
