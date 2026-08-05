package com.financialrag.backend.report;

public interface ReportJobQueue {

    void enqueue(ReportJob job);
}
