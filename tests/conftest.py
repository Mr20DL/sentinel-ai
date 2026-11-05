import os

os.environ["SENTINEL_LLM_PROVIDER"] = "heuristic"
if os.environ.get("SENTINEL_RAG_INTEGRATION") != "1":
    os.environ.pop("DATABASE_URL", None)
    os.environ["SENTINEL_EMBEDDING_PROVIDER"] = "disabled"
