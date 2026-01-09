from PIL import Image
import pytesseract

def generate_image_caption(image_path: str) -> str:
    """
    Enterprise-safe vision extraction:
    OCR-first + semantic fallback placeholder
    (LLM/Vision models can replace later)
    """
    try:
        image = Image.open(image_path)
        ocr_text = pytesseract.image_to_string(image).strip()

        if ocr_text:
            return f"OCR Extracted Content: {ocr_text}"

        return "Image contains non-textual visual information (diagram/chart)."

    except Exception as e:
        return f"Image processing error: {str(e)}"
