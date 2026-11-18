
from pathlib import Path
import pymupdf
import pytesseract
from PIL import Image
import io

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_pdf_with_ocr(file_path):
    file_path = Path(file_path)

    pages = []

    with pymupdf.open(file_path) as document:
        for page_number, page in enumerate(document, start=1):

            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(2, 2),
                alpha=False
            )

            image = Image.open(
                io.BytesIO(pix.tobytes("png"))
            )

            text = pytesseract.image_to_string(
                image,
                lang="eng"
            )

            pages.append({
                "page_number": page_number,
                "text": text.strip()
            })

    return {
        "file_name": file_path.name,
        "total_pages": len(pages),
        "pages": pages,
        "total_text_chars": sum(
            len(page["text"]) for page in pages
        )
    }
