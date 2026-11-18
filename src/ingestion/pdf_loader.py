
from pathlib import Path
import pymupdf


def load_pdf(file_path):
    file_path = Path(file_path)

    try:
        pages = []
        total_text_chars = 0

        with pymupdf.open(file_path) as document:
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                total_text_chars += len(text)

                pages.append({
                    "page_number": page_number,
                    "text": text
                })

        return {
            "file_name": file_path.name,
            "total_pages": len(pages),
            "total_text_chars": total_text_chars,
            "pages": pages
        }

    except Exception as error:
        print(f"Error loading PDF {file_path.name}: {error}")
        return None
