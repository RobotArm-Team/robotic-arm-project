package com.robotarm.management.api;

import com.robotarm.management.dto.ApiModels.StatisticsSummary;
import com.robotarm.management.service.StatisticsService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/statistics")
public class StatisticsController {

    private final StatisticsService statisticsService;

    public StatisticsController(StatisticsService statisticsService) {
        this.statisticsService = statisticsService;
    }

    @GetMapping("/summary")
    public StatisticsSummary summary() {
        return statisticsService.summary();
    }
}
