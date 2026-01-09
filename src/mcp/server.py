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


# -------- MCP Tool Schema --------
class QueryPDFRequest(BaseModel):
    query: str
    top_k: int = 5
    user_email: Optional[str] = None


class QueryPDFResponse(BaseModel):
    important_info_detected: bool
    images_present: bool
    documents: List[str]


# -------- MCP Tool Endpoint --------
@app.post("/tools/query_enterprise_pdf", response_model=QueryPDFResponse)
def query_enterprise_pdf(request: QueryPDFRequest):
    state = supervisor.run(
        query=request.query,
        top_k=request.top_k,
        user_email=request.user_email
    )

    return QueryPDFResponse(
        important_info_detected=state.get("important_info_detected", False),
        images_present=state.get("images_present", False),
        documents=[
            doc.page_content[:500]
            for doc in state.get("documents", [])
        ]
    )



if __name__ == "__main__":
    uvicorn.run("src.mcp.server:app", host="0.0.0.0", port=3333, reload=False)
