from typing import List
from pydantic import BaseModel
from langchain_core.documents import Document

from ..retrieval_mode.retrieval import retrieval_node
#from supervisor_graph import SupervisorState

from ..retrieval_mode.importance_agent import detect_important_information

from ..retrieval_mode.email_agent import send_email_notification
from ..retrieval_mode.mlflow_logger import log_rag_interaction
from langgraph.graph import StateGraph, END

from ..pdf_ingestion.vision.vision_agent import vision_agent_enrich


class SupervisorState(BaseModel):
    query: str
    top_k: int
    user_email: str | None = None

    documents: List[Document] = []

    important_info_detected: bool = False
    images_present: bool = False

    response_text: str = ""

def retrieval_agent(state: SupervisorState) -> SupervisorState:
    retrieval_state = {
        "query": state.query,
        "top_k": state.top_k
    }

    result = retrieval_node(type("Tmp", (), retrieval_state))
    state.documents = result.documents
    return state


def importance_agent_node(state: SupervisorState) -> SupervisorState:
    texts = [doc.page_content for doc in state.documents]
    state.important_info_detected = detect_important_information(texts)
    return state

def image_agent_node(state: SupervisorState) -> SupervisorState:
    state.images_present = any(
        doc.metadata.get("type") == "image"
        for doc in state.documents
    )
    return state

def vision_agent_node(state: SupervisorState) -> SupervisorState:
    state.documents = vision_agent_enrich(state.documents)
    return state



def audit_and_notify_agent(state: SupervisorState) -> SupervisorState:
    texts = [doc.page_content for doc in state.documents]
    pdf_sources = list(
        {doc.metadata.get("pdf_name", "unknown") for doc in state.documents}
    )

    log_rag_interaction(
        query=state.query,
        response="\n".join(texts[:3]),
        retrieved_chunks=len(state.documents),
        pdf_sources=pdf_sources,
        flags={
            "important_info_detected": state.important_info_detected,
            "images_present": state.images_present
        }
    )

    if state.user_email and (state.important_info_detected or state.images_present):
        send_email_notification(
            to_email=state.user_email,
            subject="Enterprise RAG Alert",
            body=f"""
Query: {state.query}
PDFs: {', '.join(pdf_sources)}
Important Info: {state.important_info_detected}
Images Present: {state.images_present}
"""
        )

    return state

def build_supervisor_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("retrieve", retrieval_agent)
    graph.add_node("vision", vision_agent_node)
    graph.add_node("importance", importance_agent_node)
    graph.add_node("image_check", image_agent_node)
    graph.add_node("audit_notify", audit_and_notify_agent)

    graph.set_entry_point("retrieve")

    graph.add_edge("retrieve", "vision")
    graph.add_edge("vision", "importance")
    graph.add_edge("importance", "image_check")
    graph.add_edge("image_check", "audit_notify")
    graph.add_edge("audit_notify", END)

    return graph.compile()


class SupervisorService:
    def __init__(self):
        self.graph = build_supervisor_graph()

    def run(self, query: str, top_k: int = 5, user_email: str | None = None):
        state = SupervisorState(
            query=query,
            top_k=top_k,
            user_email=user_email
        )
        return self.graph.invoke(state)
