package com.robotarm.management.api;

import com.robotarm.management.dto.ApiModels.SafetyStopRequest;
import com.robotarm.management.dto.ApiModels.SafetyStopResult;
import com.robotarm.management.service.SafetyService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/safety")
public class SafetyController {

    private final SafetyService safetyService;

    public SafetyController(SafetyService safetyService) {
        this.safetyService = safetyService;
    }

    @PostMapping("/stop")
    public ResponseEntity<SafetyStopResult> stop(@Valid @RequestBody SafetyStopRequest request) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(safetyService.requestStop(request.reason()));
    }
}
