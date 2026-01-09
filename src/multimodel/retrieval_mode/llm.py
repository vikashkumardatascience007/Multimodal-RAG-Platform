"""
llm.py

Step 6: LLM Answer Generation Layer

Responsibilities:
- Accept retrieved documents + user query
- Generate grounded answer using local Ollama model
- NO retrieval logic
- NO orchestration logic
"""

from typing import List
from pydantic import BaseModel, Field

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# ------------------------------------------------------------------
# Pydantic Contracts (UI / MCP / API Safe)
# ------------------------------------------------------------------

class LLMRequest(BaseModel):
    query: str = Field(..., description="User question")
    context_docs: List[str] = Field(..., description="Retrieved document chunks")


class LLMResponse(BaseModel):
    answer: str


# ------------------------------------------------------------------
# Ollama Model Configuration
# ------------------------------------------------------------------

llm = ChatOllama(
    model="llama3",
    temperature=0.1
)


# ------------------------------------------------------------------
# Prompt Template (Enterprise Grounded RAG)
# ------------------------------------------------------------------

PROMPT = ChatPromptTemplate.from_template(
    """
You are an enterprise assistant.

Answer the user's question using ONLY the provided context.
If the answer is not present in the context, say:
"I do not have enough information in the provided documents."

Context:
---------
{context}

Question:
---------
{question}

Answer:
"""
)


# ------------------------------------------------------------------
# LLM Answer Generator
# ------------------------------------------------------------------

def generate_answer(request: LLMRequest) -> LLMResponse:
    """
    Generates a final answer from retrieved documents.
    """

    context = "\n\n".join(request.context_docs)

    chain = PROMPT | llm | StrOutputParser()

    answer = chain.invoke(
        {
            "context": context,
            "question": request.query
        }
    )

    return LLMResponse(answer=answer.strip())


# ------------------------------------------------------------------
# Smoke Test
# ------------------------------------------------------------------

if __name__ == "__main__":
    sample_docs = [
        "Operating profit is calculated as revenue minus operating expenses.",
        "It excludes interest and tax expenses."
    ]

    response = generate_answer(
        LLMRequest(
            query="What is operating profit?",
            context_docs=sample_docs
        )
    )

    print("\n[LLM ANSWER]")
    print(response.answer)
