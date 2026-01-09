import mlflow
import uuid
from datetime import datetime

mlflow.set_tracking_uri("http://127.0.0.1:5006")
mlflow.set_experiment("Enterprise-RAG-PDF-latest-2334")

def log_rag_interaction(
    query: str,
    response: str,
    retrieved_chunks: int,
    pdf_sources: list,
    flags: dict
):
    run_name = f"rag-run-{uuid.uuid4().hex[:8]}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("query", query)
        mlflow.log_param("retrieved_chunks", retrieved_chunks)
        mlflow.log_param("pdf_sources", ",".join(pdf_sources))
        mlflow.log_param("timestamp", datetime.utcnow().isoformat())

        for k, v in flags.items():
            mlflow.log_param(k, v)

        mlflow.log_text(response, artifact_file="llm_response.txt")
