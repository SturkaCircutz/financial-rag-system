package com.financialrag.backend.report;

import java.util.concurrent.Executor;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "reports.queue", name = "mode", havingValue = "memory", matchIfMissing = true)
public class InMemoryReportJobQueue implements ReportJobQueue {

    private final Executor reportExecutor;
    private final ReportJobProcessor reportJobProcessor;

    public InMemoryReportJobQueue(
            @Qualifier("reportExecutor") Executor reportExecutor,
            ReportJobProcessor reportJobProcessor) {
        this.reportExecutor = reportExecutor;
        this.reportJobProcessor = reportJobProcessor;
    }

    @Override
    public void enqueue(ReportJob job) {
        reportExecutor.execute(() -> reportJobProcessor.process(job));
    }
}
