import uuid
from pathlib import Path
from langchain_core.documents import Document

def build_image_documents(image_dir: Path, pdf_name: str):
    image_docs = []

    for img_path in image_dir.glob(f"{pdf_name}_*.png"):
        image_docs.append(
            Document(
                page_content="",  # filled by captioner
                metadata={
                    "pdf_name": pdf_name,
                    "type": "image",
                    "image_path": str(img_path)
                }
            )
        )

    return image_docs
