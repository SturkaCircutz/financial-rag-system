from langgraph.graph import END, START, StateGraph

from rag_service.models import GenerateReportRequest, GenerateReportResponse, SourceFilter
from rag_service.nodes import (
    build_context,
    collect_earnings,
    collect_news,
    collect_sec,
    generate_report,
    pass_through,
    plan_request,
    rerank_chunks,
    retrieve_chunks,
    validate_report,
)
from rag_service.state import RagGraphState


def build_graph():
    graph = StateGraph(RagGraphState)
    graph.add_node("plan_request", plan_request)
    graph.add_node("sec_agent", collect_sec)
    graph.add_node("news_router", pass_through)
    graph.add_node("news_agent", collect_news)
    graph.add_node("earnings_router", pass_through)
    graph.add_node("earnings_agent", collect_earnings)
    graph.add_node("hybrid_retriever", retrieve_chunks)
    graph.add_node("reranker", rerank_chunks)
    graph.add_node("context_builder", build_context)
    graph.add_node("llm_generation", generate_report)
    graph.add_node("report_validation", validate_report)

    graph.add_edge(START, "plan_request")
    graph.add_conditional_edges(
        "plan_request",
        route_sec,
        {"run": "sec_agent", "skip": "news_router"},
    )
    graph.add_edge("sec_agent", "news_router")
    graph.add_conditional_edges(
        "news_router",
        route_news,
        {"run": "news_agent", "skip": "earnings_router"},
    )
    graph.add_edge("news_agent", "earnings_router")
    graph.add_conditional_edges(
        "earnings_router",
        route_earnings,
        {"run": "earnings_agent", "skip": "hybrid_retriever"},
    )
    graph.add_edge("earnings_agent", "hybrid_retriever")
    graph.add_edge("hybrid_retriever", "reranker")
    graph.add_edge("reranker", "context_builder")
    graph.add_edge("context_builder", "llm_generation")
    graph.add_edge("llm_generation", "report_validation")
    graph.add_edge("report_validation", END)
    return graph.compile()


def generate_report_state(request: GenerateReportRequest) -> RagGraphState:
    return build_graph().invoke({"request": request})


def generate_report_from_graph(request: GenerateReportRequest) -> GenerateReportResponse:
    return generate_report_state(request)["response"]


def route_sec(state: RagGraphState) -> str:
    return route_source(state, SourceFilter.SEC)


def route_news(state: RagGraphState) -> str:
    return route_source(state, SourceFilter.NEWS)


def route_earnings(state: RagGraphState) -> str:
    return route_source(state, SourceFilter.EARNINGS)


def route_source(state: RagGraphState, source_filter: SourceFilter) -> str:
    return "run" if source_filter in state.get("source_filters", []) else "skip"
