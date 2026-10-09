from src.domain.state import AgentState, TelemetryEvent

def ingestion_node(state: AgentState) -> dict:
    event = state["raw_event"]
    message = f"[IngestionNode] Received event from service '{event.service_name}'."
    return {"audit_logs": [message]}

def analysis_node(state: AgentState) -> dict:
    event = state["raw_event"]
    
    if event.log_level in ("ERROR", "CRITICAL"):
        is_anomaly = True
        score = 0.9
    else:
        is_anomaly=False
        score=0.1
    
    message = f"[AnalysisNode] Evaluated anomaly status: {is_anomaly} (score: {score})."
    
    return {
        "is_anomaly" : is_anomaly, 
        "anomaly_score" : score,
        "audit_logs" : [message]
    }

def context_node(state: AgentState) -> dict:
    event = state["raw_event"]
    mock_history = [f"Previous incident in {event.service_name} resolved by restarting the pool."]
    
    message = f"[ContextNode] Retrieved {len(mock_history)} historical records."
    
    return {
        "historical_context": mock_history,
        "audit_logs": [message]
    }

def response_node(state: AgentState) -> dict:
    event = state["raw_event"]
    is_anomaly = state.get("is_anomaly", False)
    
    root_cause = f"Critical log level detected in {event.service_name}" if is_anomaly else "Normal activity"
    recommendation = "Restart application connection pool and monitor latency." if is_anomaly else "No action required."
    
    message = "[ResponseNode] Diagnosis and recommendation generated."
    
    return {
        "root_cause_analysis": root_cause,
        "recommended_action": recommendation,
        "audit_logs": [message]
    }