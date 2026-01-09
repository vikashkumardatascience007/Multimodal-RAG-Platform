from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
from ..multimodel.retrieval_mode.supervisor_graph import SupervisorService

app = FastAPI(
    title="Enterprise RAG MCP Server",
    description="MCP-compatible tool server for enterprise RAG",
    version="1.0.0"
)

supervisor = SupervisorService()

# ---------------- MCP TOOL ----------------
class QueryPDFRequest(BaseModel):
    query: str
    top_k: int = 5
    user_email: Optional[str] = None


class QueryPDFResponse(BaseModel):
    important_info_detected: bool
    images_present: bool
    documents: List[str]


@app.post("/tools/query_enterprise_pdf", response_model=QueryPDFResponse)
def query_enterprise_pdf(request: QueryPDFRequest):
    state = supervisor.run(
        query=request.query,
        top_k=request.top_k,
        user_email=request.user_email
    )

    documents = state.get("documents", [])
    print('----------------------------------------------------------------------------')
    print(documents)

    if not documents:
        return QueryPDFResponse(
            important_info_detected=False,
            images_present=False,
            documents=[
                "I don’t know based on the provided documents. "
                "The uploaded PDFs do not contain relevant information for this question."
            ]
        )

     # Ensure each document is a string
    safe_docs = []
    for doc in documents:
        if hasattr(doc, "page_content"):
            safe_docs.append(doc.page_content[:500])
        elif isinstance(doc, str):
            safe_docs.append(doc[:500])
        else:
            safe_docs.append(str(doc)[:500])

    return QueryPDFResponse(
        important_info_detected=state.get("important_info_detected", False),
        images_present=state.get("images_present", False),
        documents=safe_docs
    )



# ---------------- OPENAI ADAPTER ----------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False

@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "enterprise-rag",
                "object": "model",
                "owned_by": "enterprise"
            }
        ]
    }


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionRequest):
    user_query = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_query = msg.content
            break

    state = supervisor.run(query=user_query, top_k=5)

    docs = state.get("documents", [])
    important = state.get("important_info_detected", False)
    images = state.get("images_present", False)

    response_text = f"""
Enterprise Answer

Important Info: {important}
Images Present: {images}

Context:
{chr(10).join([d.page_content[:500] for d in docs])}
""".strip()

    return {
        "id": "chatcmpl-enterprise",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }
        ]
    }


if __name__ == "__main__":
    uvicorn.run("src.mcp.server:app", host="0.0.0.0", port=3333)
