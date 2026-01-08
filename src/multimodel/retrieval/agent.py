"""
agents.py

Step 5: Multi-Agent orchestration for notifications & retrieval.
Compatible with MCP, FastAPI, and LangGraph workflow.
"""

from typing import List
from pydantic import BaseModel
from retrieval import RetrievalService, RetrievalRequest, RetrievalResponse
from pathlib import Path
import smtplib
from email.message import EmailMessage

# ---------------- Agent Pydantic Models ----------------
class NotificationRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str

# ---------------- Helper Email Function ----------------
def send_email(request: NotificationRequest):
    """
    Enterprise-ready SMTP send.
    Replace with company SMTP config or MCP server integration.
    """
    msg = EmailMessage()
    msg["From"] = "noreply@company.com"
    msg["To"] = request.recipient_email
    msg["Subject"] = request.subject
    msg.set_content(request.body)

    # Example SMTP (replace with real credentials / server)
    try:
        with smtplib.SMTP("localhost") as smtp:
            smtp.send_message(msg)
        print(f"[DEBUG] Email sent to {request.recipient_email}")
    except Exception as e:
        print(f"[ERROR] Could not send email: {e}")

# ---------------- Image Alert Agent ----------------
def image_alert_agent(pdf_name: str, image_paths: List[str], user_email: str):
    """
    Checks if PDF contains images and sends notification.
    """
    if not image_paths:
        return

    body = f"PDF '{pdf_name}' contains {len(image_paths)} images. Please review."
    send_email(NotificationRequest(
        recipient_email=user_email,
        subject=f"Images detected in PDF: {pdf_name}",
        body=body
    ))

# ---------------- Important Info Agent ----------------
def important_info_agent(pdf_name: str, metadata: dict, user_email: str):
    """
    Sends email if metadata indicates critical information.
    Example criteria: 'financial' or 'legal' category flagged as important.
    """
    category = metadata.get("category", "").lower()
    critical_flag = metadata.get("critical", False)

    if critical_flag or category in ["financial", "legal"]:
        body = f"PDF '{pdf_name}' flagged as important (Category: {category})."
        send_email(NotificationRequest(
            recipient_email=user_email,
            subject=f"Important PDF Alert: {pdf_name}",
            body=body
        ))

# ---------------- Retrieval Agent ----------------
class RetrievalAgent:
    """
    Wraps Step 4 RetrievalService for agent orchestration.
    Can be called by LangGraph or MCP.
    """
    def __init__(self):
        self.service = RetrievalService()

    def query(self, user_query: str, top_k: int = 5) -> List[str]:
        response: RetrievalResponse = self.service.query(
            RetrievalRequest(query=user_query, top_k=top_k)
        )
        return response.documents

# ---------------- Example Orchestration ----------------
def orchestrate_pdf_alert(pdf_name: str, image_paths: List[str], metadata: dict, user_email: str, query: str):
    """
    Example end-to-end orchestration.
    1. Sends alerts if images exist or PDF flagged important
    2. Executes retrieval query
    """
    # Step 1: Agents for alerts
    image_alert_agent(pdf_name, image_paths, user_email)
    important_info_agent(pdf_name, metadata, user_email)

    # Step 2: Retrieval
    retrieval_agent = RetrievalAgent()
    results = retrieval_agent.query(user_query=query)
    
    print(f"[DEBUG] Retrieved {len(results)} documents for query '{query}'")
    return results

# ---------------- Smoke Test ----------------
if __name__ == "__main__":
    sample_pdf_name = "financial_report_2025"
    sample_images = ["img_1.png", "img_2.png"]
    sample_metadata = {"category": "bank", "critical": True}
    user_email = "vk00794007@gmail.com"
    query = "Operating profit analysis"

    retrieved_docs = orchestrate_pdf_alert(
        pdf_name=sample_pdf_name,
        image_paths=sample_images,
        metadata=sample_metadata,
        user_email=user_email,
        query=query
    )

    for i, doc in enumerate(retrieved_docs, 1):
        print(f"\n--- Retrieved Doc {i} ---\n{doc[:500]}")
