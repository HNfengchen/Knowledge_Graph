from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from kg_system.reasoning.nodes import (
    decide_node,
    generate_node,
    reason_node,
    retrieve_node,
    route_after_decide,
)
from kg_system.reasoning.state import ReasonerState


def build_reasoning_graph() -> CompiledStateGraph:
    """装配 StateGraph 并 compile。节点函数本身在骨架内会 raise。"""
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
