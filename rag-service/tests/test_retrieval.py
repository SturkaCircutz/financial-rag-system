from rag_service.models import SourceFilter
from rag_service.retrieval import rank_agent_results
from rag_service.state import AgentResult


def test_rank_agent_results_scores_question_terms_first():
    agent_results: list[AgentResult] = [
        {
            "source_type": SourceFilter.SEC,
            "status": "completed",
            "evidence_id": "generic",
            "title": "Generic risk evidence",
            "url": "https://example.com/generic",
            "text": "Revenue, margins, and liquidity are useful filing review topics.",
        },
        {
            "source_type": SourceFilter.SEC,
            "status": "completed",
            "evidence_id": "export-controls",
            "title": "Export controls and risk factors",
            "url": "https://example.com/export-controls",
            "text": "Export controls create supply and demand risk for AI accelerator shipments.",
        },
    ]

    ranked_chunks = rank_agent_results(agent_results, "export controls risk")

    assert ranked_chunks[0]["evidence_id"] == "export-controls"
    assert ranked_chunks[0]["score"] > ranked_chunks[1]["score"]
