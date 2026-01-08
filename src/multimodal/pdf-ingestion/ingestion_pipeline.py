import json
from pathlib import Path
import fitz   
import pdfplumber
from PIL import Image
import pytesseract

# -----------------------------
# PATH CONFIGURATION
# -----------------------------
BASE_DIR = Path(__file__).parent
RAW_PDF_DIR = BASE_DIR / "raw_pdfs"
PROCESSED_DIR = BASE_DIR / "processed_pdfs"
METADATA_DIR = BASE_DIR / "metadata"
CATALOG_FILE = METADATA_DIR / "pdf_catalog.json"

TEXT_DIR = PROCESSED_DIR / "text"
TABLE_DIR = PROCESSED_DIR / "tables"
IMAGE_DIR = PROCESSED_DIR / "images"

for d in [TEXT_DIR, TABLE_DIR, IMAGE_DIR, METADATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# -----------------------------
# STEP 1: BUILD PDF CATALOG
# -----------------------------
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


# -----------------------------
# STEP 2: EXTRACTION FUNCTIONS
# -----------------------------
def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []

    for page_num, page in enumerate(doc):
        text = page.get_text().strip()

        if not text:
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)

        pages.append({
            "page": page_num + 1,
            "text": text
        })

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

    for page_index in range(len(doc)):
        page = doc[page_index]
        image_list = page.get_images(full=True)

        for img_index, img in enumerate(image_list):
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


# -----------------------------
# STEP 2: PROCESS SINGLE PDF
# -----------------------------
def process_pdf(record):
    pdf_path = record["path"]
    pdf_name = Path(pdf_path).stem

    text_pages = extract_text(pdf_path)
    tables = extract_tables(pdf_path)
    images = extract_images(pdf_path, pdf_name)

    with open(TEXT_DIR / f"{pdf_name}.json", "w", encoding="utf-8") as f:
        json.dump(text_pages, f, indent=4)

    with open(TABLE_DIR / f"{pdf_name}.json", "w", encoding="utf-8") as f:
        json.dump(tables, f, indent=4)

    record["ingestion_status"] = "COMPLETED"
    record["pages"] = len(text_pages)
    record["tables"] = len(tables)
    record["images"] = len(images)


# -----------------------------
# PIPELINE ORCHESTRATOR
# -----------------------------
def run_pipeline():
    records = build_pdf_catalog()

    for record in records:
        if record["ingestion_status"] == "PENDING":
            process_pdf(record)

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    run_pipeline()
    print("Step 1 & Step 2 completed successfully.")
