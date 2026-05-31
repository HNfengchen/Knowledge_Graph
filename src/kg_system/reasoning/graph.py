from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from kg_system.builder.extractor import EntityExtractor
from kg_system.kg_query.service import KGQueryService
from kg_system.reasoning.nodes import (
    _make_generate_node,
    _make_reason_node,
    _make_retrieve_node,
    decide_node,
    route_after_decide,
)
from kg_system.reasoning.state import ReasonerState


def build_reasoning_graph(
    llm: BaseChatModel,
    kg_service: KGQueryService,
) -> CompiledStateGraph:
    """装配 StateGraph 并 compile。注入 llm 和查询服务依赖。"""
    extractor = EntityExtractor(llm)
    retrieve_node = _make_retrieve_node(kg_service, extractor)
    reason_node = _make_reason_node(llm)
    generate_node = _make_generate_node(llm)

    workflow: StateGraph = StateGraph(ReasonerState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("reason", reason_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("generate", generate_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "reason")
    workflow.add_edge("reason", "decide")
    workflow.add_conditional_edges(
        "decide",
        route_after_decide,
        {
            "retrieve": "retrieve",
            "reason": "reason",
            "generate": "generate",
            "end": END,
        },
    )
    workflow.add_edge("generate", END)
    return workflow.compile()
