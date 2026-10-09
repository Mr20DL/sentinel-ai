from langgraph.graph import StateGraph, END
from src.domain.state import AgentState
from src.domain.nodes import (
    ingestion_node,
    analysis_node,
    context_node,
    response_node,
)

def should_continue(state: AgentState) -> str:
    if state.get("is_anomaly", False):
        return "context_node"
    return END
    
def create_sentinel_graph():
    # Instanciar el grafo con el esquema de AgentState
    workflow = StateGraph(AgentState)
    
    #Registrar los 4 nodos con sus funciones
    workflow.add_node("ingestion_node", ingestion_node)
    workflow.add_node("analysis_node", analysis_node)
    workflow.add_node("context_node", context_node)
    workflow.add_node("response_node", response_node)
    
    #Definir por dónde arranca el grafo
    workflow.set_entry_point("ingestion_node")
    
    #Flujo directo desde Ingesta siempre va a Análisis
    workflow.add_edge("ingestion_node", "analysis_node")
    
    #Flujo condicional desde Análisis a Contexto o fin
    workflow.add_conditional_edges(
        "analysis_node",
        should_continue,
        {
            "context_node": "context_node",
            END: END,
        },
    )
    
    #Si pasa a Contexto, sigue obligatoriamente a Respuesta y luego finaliza
    workflow.add_edge("context_node", "response_node")
    workflow.add_edge("response_node", END)
    
    #Compila y retorna la aplicación ejecutable
    return workflow.compile()

# Instancia exportable del ejecutable
sentinel_app = create_sentinel_graph()
