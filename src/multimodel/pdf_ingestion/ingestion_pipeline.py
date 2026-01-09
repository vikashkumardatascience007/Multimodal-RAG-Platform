"""
ingestion.py

Enterprise-grade PDF ingestion pipeline for Multimodal RAG platform.
Steps:
1. Catalog PDFs
2. Extract text, tables, images (with OCR fallback)
3. Chunk text/tables
4. Store chunks in Chroma vector store
"""

import json
from pathlib import Path
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import pytesseract
import uuid
import tiktoken

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from vision.image_embedder import build_image_documents
from vision.vision_agent import vision_agent_enrich
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings


# ---------------- Directories ----------------
BASE_DIR = Path(__file__).parent
# points to src/
BASE_DIR1 = Path(__file__).resolve().parent.parent  

RAW_PDF_DIR = BASE_DIR / "raw_pdfs"
PROCESSED_DIR = BASE_DIR / "processed_pdfs"
METADATA_DIR = BASE_DIR / "metadata"
CHUNK_DIR = PROCESSED_DIR / "chunks"
TEXT_DIR = PROCESSED_DIR / "text"
TABLE_DIR = PROCESSED_DIR / "tables"
IMAGE_DIR = PROCESSED_DIR / "images"
VECTOR_DB_DIR = BASE_DIR1 / "vector_store" / "chroma"
CATALOG_FILE = METADATA_DIR / "pdf_catalog.json"

for d in [RAW_PDF_DIR, PROCESSED_DIR, METADATA_DIR, CHUNK_DIR, TEXT_DIR, TABLE_DIR, IMAGE_DIR, VECTOR_DB_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ---------------- Embeddings & Tokenizer ----------------
embedding = HuggingFaceEmbeddings(
    model_name="./all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"}
)
tokenizer = tiktoken.get_encoding("cl100k_base")

# ---------------- Step 1: Build PDF Catalog ----------------
def build_pdf_catalog():
    records = []
    for category in RAW_PDF_DIR.iterdir():
        if not category.is_dir():
            continue
        for pdf in category.glob("*.pdf"):
            records.append({
                "pdf_name": pdf.name,
                "category": category.name,
                "path": str(pdf.resolve()),
                "ingestion_status": "PENDING"
            })
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)
    return records

# ---------------- Step 2: Extraction Functions ----------------
def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for page_num, page in enumerate(doc):
        text = page.get_text().strip()
        if not text:
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)
        pages.append({"page": page_num + 1, "text": text})
    return pages

def extract_tables(pdf_path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            extracted = page.extract_tables()
            for idx, table in enumerate(extracted):
                tables.append({
                    "page": page_num + 1,
                    "table_id": f"table_{page_num+1}_{idx}",
                    "rows": table
                })
    return tables

def extract_images(pdf_path, pdf_name):
    images = []
    doc = fitz.open(pdf_path)
    for page_index, page in enumerate(doc):
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_name = f"{pdf_name}_p{page_index+1}_{img_index}.png"
            image_path = IMAGE_DIR / image_name
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            images.append({
                "page": page_index + 1,
                "image_name": image_name,
                "path": str(image_path)
            })
    return images

def ingest_image_embeddings(pdf_name: str):
    """
    One-time image understanding + embedding into Chroma.
    Called during ingestion only.
    """
    image_dir = IMAGE_DIR

    embedding = HuggingFaceEmbeddings(
        model_name="./all-MiniLM-L6-v2"
    )

    vectordb = Chroma(
        persist_directory=str(BASE_DIR / "vector_store" / "chroma"),
        collection_name="enterprise_rag_documents",
        embedding_function=embedding
    )

    # Build image documents
    image_docs = build_image_documents(image_dir, pdf_name)

    if not image_docs:
        return

    # Enrich with OCR / captions
    enriched_docs = vision_agent_enrich(image_docs)

    vectordb.add_documents(enriched_docs)
    vectordb.persist()
    print('images also ingected')


# ---------------- Step 2B: Process Single PDF ----------------
def process_pdf(record):
    pdf_path = record["path"]
    pdf_name = Path(pdf_path).stem

    text_pages = extract_text(pdf_path)
    tables = extract_tables(pdf_path)
    images = extract_images(pdf_path, pdf_name)

    # Save processed data
    with open(TEXT_DIR / f"{pdf_name}.json", "w", encoding="utf-8") as f:
        json.dump(text_pages, f, indent=4)
    with open(TABLE_DIR / f"{pdf_name}.json", "w", encoding="utf-8") as f:
        json.dump(tables, f, indent=4)

    record.update({
        "ingestion_status": "COMPLETED",
        "pages": len(text_pages),
        "tables": len(tables),
        "images": len(images)
    })

# ---------------- Step 3: Chunking ----------------
def chunk_text(text, chunk_size=500, overlap=50):
    tokens = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunks.append(tokenizer.decode(chunk_tokens))
        start += chunk_size - overlap
    return chunks

def build_chunks(pdf_name):
    chunk_records = []

    # Text chunks
    with open(TEXT_DIR / f"{pdf_name}.json", "r", encoding="utf-8") as f:
        pages = json.load(f)

    for page in pages:
        for chunk in chunk_text(page["text"]):
            chunk_records.append({
                "id": str(uuid.uuid4()),
                "document": chunk,
                "metadata": {"pdf_name": pdf_name, "type": "text", "page": page["page"]}
            })

    # Table chunks
    table_file = TABLE_DIR / f"{pdf_name}.json"
    if table_file.exists():
        with open(table_file, "r", encoding="utf-8") as f:
            tables = json.load(f)
        for table in tables:
            table_text = "\n".join([
                " | ".join([str(cell).strip() if cell else "" for cell in row])
                for row in table["rows"] if row and any(cell is not None for cell in row)
            ])
            chunk_records.append({
                "id": str(uuid.uuid4()),
                "document": table_text,
                "metadata": {"pdf_name": pdf_name, "type": "table", "page": table["page"]}
            })

    # Save chunk file
    with open(CHUNK_DIR / f"{pdf_name}.json", "w", encoding="utf-8") as f:
        json.dump(chunk_records, f, indent=4)

    print(f"[DEBUG] {len(chunk_records)} chunks built for {pdf_name}")
    return chunk_records

# ---------------- Step 4: Store in Chroma ----------------
def store_chunks_in_chroma(chunks):
    if not chunks:
        print("[WARNING] No chunks to store")
        return

    texts = [c["document"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    vectordb = Chroma.from_texts(
        texts=texts,
        embedding=embedding,
        metadatas=metadatas,
        persist_directory=str(VECTOR_DB_DIR),
        collection_name="enterprise_rag_documents"
    )

    vectordb.persist()
    print(f"[DEBUG] {len(chunks)} chunks stored in Chroma.")

# ---------------- Pipeline Orchestrator ----------------
def run_pipeline():
    records = build_pdf_catalog()
    for record in records:
        if record["ingestion_status"] == "PENDING":
            process_pdf(record)
            pdf_name = Path(record["pdf_name"]).stem
            chunks = build_chunks(pdf_name)
            store_chunks_in_chroma(chunks)
            ingest_image_embeddings(pdf_name)
            record["chunks"] = len(chunks)
            record["ingestion_status"] = "COMPLETED"

    # Update catalog
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)

# ---------------- Entry Point ----------------
if __name__ == "__main__":
    run_pipeline()
    print("PDF and images ingestion completed successfully.")
