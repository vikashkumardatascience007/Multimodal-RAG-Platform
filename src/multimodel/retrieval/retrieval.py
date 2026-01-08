"""
retrieval.py

Enterprise-grade retrieval layer for a Multimodal RAG system.
"""

from typing import List
from pydantic import BaseModel, Field
from pathlib import Path

from langgraph.graph import StateGraph, END
from langchain_core.documents import Document

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma  # keep your current package

# ---------------- Configuration ----------------
BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_EMBEDDING_MODEL_PATH = "./all-MiniLM-L6-v2"
CHROMA_DB_PATH = str(BASE_DIR / "vector_store" / "chroma")  # Windows-safe
COLLECTION_NAME = "enterprise_rag_documents"  # match ingestion

# ---------------- Pydantic Models ----------------
class RetrievalRequest(BaseModel):
    query: str = Field(..., description="User search query")
    top_k: int = Field(default=5, ge=1, le=20)

class RetrievalResponse(BaseModel):
    query: str
    documents: List[str]

class RetrievalState(BaseModel):
    query: str
    top_k: int
    documents: List[Document] = []

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
    results = vector_db.similarity_search(
        query=state.query,
        k=state.top_k
    )

    # convert dicts to Document
    docs: List[Document] = []
    for r in results:
        if isinstance(r, Document):
            docs.append(r)
        elif isinstance(r, dict):
            docs.append(Document(
                page_content=r.get("document") or r.get("page_content") or "",
                metadata=r.get("metadata", {})
            ))
        else:
            docs.append(Document(page_content=str(r)))

    state.documents = docs
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

        # If final_state is a dict (common with LangGraph), convert it back to RetrievalState
        if isinstance(final_state, dict):
            final_state = RetrievalState(**final_state)

        # Convert all Document objects to text safely
        docs_text = [
            doc.page_content if isinstance(doc, Document) else str(doc)
            for doc in final_state.documents
        ]

        return RetrievalResponse(
            query=request.query,
            documents=docs_text
        )

# ---------------- Smoke Test ----------------
if __name__ == "__main__":
    service = RetrievalService()

    try:
        num_docs = len(vector_db._collection.get(include=["documents"])["documents"])
        print(f"[DEBUG] Vector DB contains {num_docs} documents.")
    except Exception as e:
        print(f"[DEBUG] Could not fetch collection size: {e}")

    response = service.query(
        RetrievalRequest(query="give info about OPERATING profit")
    )

    for idx, doc in enumerate(response.documents, start=1):
        print(f"\n--- Document {idx} ---\n{doc[:500]}")
