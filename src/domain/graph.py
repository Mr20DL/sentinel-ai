from langgraph.graph import StateGraph, END

from src.composition import build_default_components
from src.domain.nodes import (
    create_analysis_node,
    create_context_node,
    create_ingestion_node,
    create_response_node,
)
from src.domain.state import AgentState
from src.ports.observability import ObservabilityPort


def should_continue(state: AgentState) -> str:
    if state.get("is_anomaly", False):
        return "context_node"
    return END


def create_sentinel_graph(components: dict | None = None):
    components = components or build_default_components()
    repository = components["repository"]
    notifier = components["notifier"]
    tracker: ObservabilityPort | None = components.get("tracker")

    def tracked(node, name):
        def wrapped(state: AgentState) -> dict:
            result = node(state)
            if tracker and state.get("trace_id"):
                tracker.record_step(state["trace_id"], name, {"audit": result})
            return result

        return wrapped

    workflow = StateGraph(AgentState)

    workflow.add_node("ingestion_node", tracked(create_ingestion_node(tracker), "ingestion_node"))
    workflow.add_node("analysis_node", tracked(create_analysis_node(tracker), "analysis_node"))
    workflow.add_node("context_node", tracked(create_context_node(repository, tracker), "context_node"))
    workflow.add_node("response_node", tracked(create_response_node(notifier, tracker), "response_node"))

    workflow.set_entry_point("ingestion_node")
    workflow.add_edge("ingestion_node", "analysis_node")
    workflow.add_conditional_edges(
        "analysis_node",
        should_continue,
        {
            "context_node": "context_node",
            END: END,
        },
    )
    workflow.add_edge("context_node", "response_node")
    workflow.add_edge("response_node", END)

    return workflow.compile()


sentinel_app = create_sentinel_graph()