"""
retrieval.py

Enterprise-grade retrieval layer for a Multimodal RAG system
with Agent-based post-retrieval actions and MLflow tracking.
"""

from typing import List
from pathlib import Path
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from langchain_core.documents import Document

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from ..retrieval_mode.importance_agent import detect_important_information
from ..retrieval_mode.email_agent import send_email_notification
from ..retrieval_mode.mlflow_logger import log_rag_interaction


RELEVANCE_THRESHOLD = 0.35
# ---------------- Configuration ----------------
BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_EMBEDDING_MODEL_PATH = "./all-MiniLM-L6-v2"
CHROMA_DB_PATH = str(BASE_DIR / "vector_store" / "chroma")
COLLECTION_NAME = "enterprise_rag_documents"


# ---------------- Pydantic Models ----------------
class RetrievalRequest(BaseModel):
    query: str = Field(..., description="User search query")
    top_k: int = Field(default=5, ge=1, le=20)
    user_email: str | None = Field(default=None)


class RetrievalResponse(BaseModel):
    query: str
    documents: List[str]
    important_info_detected: bool
    images_present: bool


class RetrievalState(BaseModel):
    query: str
    top_k: int
    documents: List[Document] = []
    no_relevant_docs: bool = False



# ---------------- Vector Store ----------------
embedding_function = HuggingFaceEmbeddings(
    model_name=LOCAL_EMBEDDING_MODEL_PATH
)

vector_db = Chroma(
    collection_name=COLLECTION_NAME,
    persist_directory=CHROMA_DB_PATH,
    embedding_function=embedding_function
)


# ---------------- LangGraph Node ----------------
def retrieval_node(state: RetrievalState) -> RetrievalState:
    results = vector_db.similarity_search_with_score(
        query=state.query,
        k=state.top_k
    )

    relevant_docs = []

    print("\n[DEBUG] Retrieval scores:")
    for doc, score in results:
        print(f"Score: {score:.4f} | Preview: {doc.page_content[:120]}")

        if score <= RELEVANCE_THRESHOLD:
            relevant_docs.append(doc)

    state.documents = relevant_docs
    state.no_relevant_docs = len(relevant_docs) == 0
    print(state.no_relevant_docs,'******************', state.documents)
    return state


# ---------------- LangGraph Workflow ----------------
def build_retrieval_graph():
    graph = StateGraph(RetrievalState)
    graph.add_node("retrieve", retrieval_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", END)
    return graph.compile()


# ---------------- Public Service ----------------
class RetrievalService:
    def __init__(self):
        self.graph = build_retrieval_graph()

    def query(self, request: RetrievalRequest) -> RetrievalResponse:
        initial_state = RetrievalState(
            query=request.query,
            top_k=request.top_k
        )

        final_state = self.graph.invoke(initial_state)

        if isinstance(final_state, dict):
            final_state = RetrievalState(**final_state)

        # Extract content and metadata
        docs = final_state.documents
        docs_text = [doc.page_content for doc in docs]

        pdf_sources = list(
            {doc.metadata.get("pdf_name", "unknown") for doc in docs}
        )

        # ---------------- Agents ----------------
        important_info_detected = detect_important_information(docs_text)

        images_present = any(
            doc.metadata.get("type") == "image" for doc in docs
        )

        # ---------------- MLflow Logging ----------------
        log_rag_interaction(
            query=request.query,
            response="\n".join(docs_text[:3]),
            retrieved_chunks=len(docs),
            pdf_sources=pdf_sources,
            flags={
                "important_info_detected": important_info_detected,
                "images_present": images_present
            }
        )

        # ---------------- Email Notification ----------------
        if request.user_email and (important_info_detected or images_present):
            email_body = f"""
Enterprise RAG Alert

Query:
{request.query}

PDF Sources:
{', '.join(pdf_sources)}

Flags:
- Important Info Detected: {important_info_detected}
- Images Present: {images_present}
"""

            send_email_notification(
                to_email=request.user_email,
                subject="Enterprise RAG Alert: Important PDF Content",
                body=email_body
            )

        return RetrievalResponse(
            query=request.query,
            documents=docs_text,
            important_info_detected=important_info_detected,
            images_present=images_present
        )


# ---------------- Smoke Test ----------------
if __name__ == "__main__":
    service = RetrievalService()

    try:
        num_docs = len(
            vector_db._collection.get(include=["documents"])["documents"]
        )
        print(f"[DEBUG] Vector DB contains {num_docs} documents.")
    except Exception as e:
        print(f"[DEBUG] Could not fetch collection size: {e}")

    response = service.query(
        RetrievalRequest(
            query="give info about OPERATING profit",
            user_email="vk00794007@gmail.com"
        )
    )

    for idx, doc in enumerate(response.documents, start=1):
        print(f"\n--- Document {idx} ---\n{doc[:500]}")
