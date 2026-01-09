from ..vision.image_captioner import generate_image_caption
from langchain_core.documents import Document

def vision_agent_enrich(documents: list[Document]) -> list[Document]:
    """
    Enrich image documents with textual meaning
    """
    enriched_docs = []

    for doc in documents:
        if doc.metadata.get("type") == "image":
            image_path = doc.metadata.get("image_path")
            caption = generate_image_caption(image_path)

            enriched_docs.append(
                Document(
                    page_content=caption,
                    metadata=doc.metadata
                )
            )
        else:
            enriched_docs.append(doc)

    return enriched_docs
