from contextlib import suppress

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.composition import build_default_components
from src.domain.nodes import (
    create_analysis_node,
    create_context_node,
    create_ingestion_node,
    create_response_node,
)
from src.domain.state import AgentState
from src.ports.observability import ObservabilityPort


def should_process(state: AgentState) -> str:
    if state.get("sanitization_ok", False):
        return "analysis_node"
    return END


def should_continue(state: AgentState) -> str:
    if not state.get("sanitization_ok", False):
        return END
    if state.get("is_anomaly", False):
        return "context_node"
    return END


def _is_terminal_step(name: str, result: dict) -> bool:
    if name == "response_node":
        return True
    if name == "ingestion_node":
        return not result.get("sanitization_ok", True)
    if name == "analysis_node":
        return not result.get("is_anomaly", True)
    return False


def create_sentinel_graph(
    components: dict | None = None,
    checkpointer: MemorySaver | None = None,
):
    components = components or build_default_components()
    repository = components["repository"]
    notifier = components["notifier"]
    tracker: ObservabilityPort | None = components.get("tracker")
    diagnoser = components.get("diagnoser")

    def tracked(node, name):
        def wrapped(state: AgentState) -> dict:
            result = node(state)
            trace_id = state.get("trace_id") or result.get("trace_id")
            if tracker and trace_id:
                with suppress(Exception):
                    tracker.record_step(trace_id, name, {"audit": result})
                if _is_terminal_step(name, result):
                    with suppress(Exception):
                        tracker.finish_trace(trace_id)
            return result

        return wrapped

    workflow = StateGraph(AgentState)

    workflow.add_node("ingestion_node", tracked(create_ingestion_node(tracker), "ingestion_node"))
    workflow.add_node("analysis_node", tracked(create_analysis_node(), "analysis_node"))
    workflow.add_node("context_node", tracked(create_context_node(repository), "context_node"))
    workflow.add_node(
        "response_node",
        tracked(create_response_node(notifier, diagnoser), "response_node"),
    )

    workflow.set_entry_point("ingestion_node")
    workflow.add_conditional_edges(
        "ingestion_node",
        should_process,
        {
            "analysis_node": "analysis_node",
            END: END,
        },
    )
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

    if checkpointer is None:
        checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


sentinel_app = create_sentinel_graph()
