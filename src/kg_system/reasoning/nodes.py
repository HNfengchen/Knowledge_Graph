from __future__ import annotations

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from kg_system.builder.extractor import EntityExtractor
from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.kg_query.service import KGQueryService
from kg_system.reasoning.state import ReasonerState

log = get_logger(__name__)

SYSTEM_PROMPT = """你是一个知识图谱推理助手。基于给定的子图信息和问题，逐步推理。
请输出 JSON 格式：
{
  "thought": "你的推理过程",
  "next_action": "reason | retrieve | generate",
  "query": "如果需要进一步检索，填写实体名（可选）"
}

规则：
- 如果信息足以回答问题，next_action 设为 generate
- 如果需要更多信息，可以设为 retrieve 指定新查询词
- 如果还需要进一步推理，next_action 设为 reason"""

GENERATE_SYSTEM = """基于推理过程和图谱证据，给出最终答案。
请引用相关的图谱节点 id 作为依据。
输出 JSON 格式：{"answer": "你的回答"}"""


def _make_retrieve_node(kg_service: KGQueryService, extractor: EntityExtractor):
    async def retrieve_node(state: ReasonerState) -> ReasonerState:
        s = get_settings()
        subgraph_str = state.get("subgraph", "")
        step = state.get("step_count", 0)
        question = state.get("question", "")

        if step == 0:
            entities = await extractor.extract(question)
            entity_names = [e.name for e in entities]
            if not entity_names:
                state["subgraph"] = json.dumps({"nodes": [], "links": []}, ensure_ascii=False)
                state["reasoning_trace"] = state.get("reasoning_trace", []) + ["未识别到实体"]
                return state

            all_nodes = []
            all_links = []
            seen_node_ids = set()
            for name in entity_names:
                sg = await kg_service.query_subgraph(
                    name,
                    depth=s.REASONING_SUBGRAPH_DEPTH,
                )
                if sg and sg.nodes:
                    for n in sg.nodes:
                        if n.id not in seen_node_ids:
                            seen_node_ids.add(n.id)
                            all_nodes.append(n)
                    all_links.extend(sg.links)
                if len(all_nodes) > s.REASONING_SUBGRAPH_MAX_NODES:
                    all_nodes = all_nodes[: s.REASONING_SUBGRAPH_MAX_NODES]
                    break
            result = {"nodes": [n.model_dump() for n in all_nodes],
                      "links": [l.model_dump() for l in all_links]}
            state["subgraph"] = json.dumps(result, ensure_ascii=False)
        else:
            query = state.get("query_for_retrieve", "")
            if query:
                sg = await kg_service.query_subgraph(
                    query,
                    depth=s.REASONING_SUBGRAPH_DEPTH,
                )
                if sg and sg.nodes:
                    existing = json.loads(subgraph_str) if subgraph_str else {"nodes": [], "links": []}
                    seen = {n["id"] for n in existing.get("nodes", [])}
                    for n in sg.nodes:
                        if n.id not in seen:
                            seen.add(n.id)
                            existing["nodes"].append(n.model_dump())
                    existing["links"].extend(l.model_dump() for l in sg.links)
                    state["subgraph"] = json.dumps(existing, ensure_ascii=False)

        trace = state.get("reasoning_trace", [])
        trace.append(f"检索完成，子图含 {len(all_nodes) if step == 0 else '?'} 节点")
        state["reasoning_trace"] = trace
        return state

    return retrieve_node


def _make_reason_node(llm: BaseChatModel):
    async def reason_node(state: ReasonerState) -> ReasonerState:
        question = state.get("question", "")
        subgraph = state.get("subgraph", "{}")

        msg = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"问题：{question}\n\n子图：{subgraph}")
        ])
        content = str(msg.content)
        try:
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                parsed = {"thought": content, "next_action": "generate"}
        except json.JSONDecodeError:
            parsed = {"thought": content, "next_action": "generate"}

        trace = state.get("reasoning_trace", [])
        trace.append(parsed.get("thought", content[:100]))
        state["reasoning_trace"] = trace
        state["next_action"] = parsed.get("next_action", "generate")
        if parsed.get("query"):
            state["query_for_retrieve"] = parsed["query"]
        return state

    return reason_node


async def decide_node(state: ReasonerState) -> ReasonerState:
    step = state.get("step_count", 0)
    max_steps = state.get("max_steps", 5)

    if step >= max_steps:
        state["next_action"] = "generate"
        trace = state.get("reasoning_trace", [])
        trace.append(f"达到最大步骤 {max_steps}，强制生成")
        state["reasoning_trace"] = trace
    return state


def _make_generate_node(llm: BaseChatModel):
    async def generate_node(state: ReasonerState) -> ReasonerState:
        question = state.get("question", "")
        subgraph = state.get("subgraph", "{}")
        trace = state.get("reasoning_trace", [])

        msg = await llm.ainvoke([
            SystemMessage(content=GENERATE_SYSTEM),
            HumanMessage(content=f"问题：{question}\n\n推理过程：{json.dumps(trace, ensure_ascii=False)}\n\n子图：{subgraph}")
        ])
        content = str(msg.content)
        try:
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                parsed = {"answer": content}
        except json.JSONDecodeError:
            parsed = {"answer": content}

        state["answer"] = parsed.get("answer", content)
        trace.append("答案已生成")
        state["reasoning_trace"] = trace
        state["next_action"] = "end"
        return state

    return generate_node


def route_after_decide(state: ReasonerState) -> str:
    return state.get("next_action", "end")
