
from pathlib import Path
from src.ingestion.pdf_loader import load_pdf

for pdf_file in Path("data").rglob("*.pdf"):
    result = load_pdf(pdf_file)

    if result is None:
        continue

    print("\nPDF:", result["file_name"])
    print("Pages:", result["total_pages"])
    print("Extracted characters:", result["total_text_chars"])

    for page in result["pages"]:
        if page["text"]:
            print(f"\nPage {page['page_number']}:")
            print(page["text"][:300])
            break

    if result["total_text_chars"] == 0:
        print("No selectable text found. OCR may be required.")
