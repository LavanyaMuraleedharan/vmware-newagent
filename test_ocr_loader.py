
from pathlib import Path
from src.ingestion.ocr_loader import extract_pdf_with_ocr

for pdf_file in Path("data").rglob("*.pdf"):

    result = extract_pdf_with_ocr(pdf_file)

    print("\nPDF:", result["file_name"])
    print("Pages:", result["total_pages"])
    print("Extracted characters:", result["total_text_chars"])

    for page in result["pages"][:2]:
        print(f"\nPage {page['page_number']}:")
        print(page["text"][:500])
