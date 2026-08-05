from fastapi import FastAPI

from rag_service.graph import generate_report_from_graph
from rag_service.models import GenerateReportRequest, GenerateReportResponse

app = FastAPI(title="Financial RAG Service", version="0.1.0")


@app.post("/v1/reports:generate", response_model=GenerateReportResponse)
def generate_report(request: GenerateReportRequest) -> GenerateReportResponse:
    return generate_report_from_graph(request)
