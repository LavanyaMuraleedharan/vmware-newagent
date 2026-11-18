from pathlib import Path
import csv
import json
import re
import sys

import fitz
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PDFS = [
    ROOT / "data" / "license1.pdf",
    ROOT / "data" / "license2.pdf"
]
OUT = DATA / "processed" / "licensing"
TEXT_DIR = OUT / "research_text"

# If Tesseract is installed in a non-standard Windows location, set this:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def ocr_pdf(pdf_path: Path):
    doc = fitz.open(pdf_path)
    pages = []
    for page_no, page in enumerate(doc, start=1):
        # Use embedded text when available; otherwise OCR the scanned page.
        text = page.get_text("text").strip()
        if not text:
            pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(image, config="--psm 6")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        pages.append({"page": page_no, "text": text})
    return pages


def write_csv_template(path: Path, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    missing = [p for p in PDFS if not p.exists()]
    if missing:
        print("Missing PDF(s):", *[str(p) for p in missing], sep="\n")
        print("Expected both PDFs inside the project's data folder.")
        sys.exit(1)

    knowledge_docs = []
    extraction_summary = []

    for pdf_path in PDFS:
        pages = ocr_pdf(pdf_path)
        combined = "\n\n".join(
            f"===== PAGE {item['page']} =====\n{item['text']}" for item in pages
        )
        txt_path = TEXT_DIR / f"{pdf_path.stem}_extracted.txt"
        txt_path.write_text(combined, encoding="utf-8")

        nonempty_pages = 0
        for item in pages:
            if item["text"].strip():
                nonempty_pages += 1
                knowledge_docs.append({
                    "document_id": f"{pdf_path.stem}_page_{item['page']:02d}",
                    "domain": "Licensing",
                    "document_type": "research_document",
                    "source_file": pdf_path.name,
                    "page": item["page"],
                    "data_origin": "research_document",
                    "text": item["text"]
                })

        extraction_summary.append({
            "source_file": pdf_path.name,
            "total_pages": len(pages),
            "pages_with_text": nonempty_pages,
            "extracted_text_file": str(txt_path.relative_to(ROOT))
        })

    jsonl_path = OUT / "licensing_research_knowledge.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for doc in knowledge_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # These are empty schemas/templates, not fabricated license records.
    write_csv_template(OUT / "license_inventory_template.csv", [
        "license_id", "software_product", "publisher", "version",
        "license_metric", "entitled_quantity", "installed_quantity",
        "assigned_quantity", "contract_start_date", "contract_end_date",
        "renewal_date", "support_maintenance_cost", "currency",
        "cost_period", "business_owner", "department", "source_system",
        "record_timestamp"
    ])

    write_csv_template(OUT / "license_events_template.csv", [
        "event_id", "event_timestamp", "event_type", "software_feature",
        "username", "hostname", "license_quantity", "vendor_daemon",
        "server_name", "denial_reason", "source_log_file"
    ])

    write_csv_template(OUT / "license_cost_reference_template.csv", [
        "software_product", "publisher", "license_metric",
        "unit_cost", "currency", "cost_period", "effective_from",
        "effective_to", "cost_source", "approval_status"
    ])

    dictionary = {
        "domain": "Licensing",
        "purpose": "Normalize software license inventory, usage events and authorized cost references for FinOps analysis.",
        "research_methodologies": [
            {
                "source": "license1.pdf",
                "method": "Analyze license-server sessions and usage over time; group by application and user; inspect concurrent usage and incomplete session records."
            },
            {
                "source": "license2.pdf",
                "method": "Parse FLEXlm OUT, IN and DENIED events; pair check-outs and check-ins; calculate elapsed usage weighted by checked-out license quantity; group by user, feature and department when mapping data exists."
            }
        ],
        "event_types": {
            "OUT": "License checked out / issued",
            "IN": "License checked in / returned",
            "DENIED": "License request denied"
        },
        "core_entities": [
            "software_product", "publisher", "license_feature", "license_metric",
            "entitlement", "installation", "assignment", "user", "host",
            "department", "license_event", "contract", "cost_reference"
        ],
        "calculations": {
            "session_duration_seconds": "checkin_timestamp - checkout_timestamp",
            "license_usage_seconds": "session_duration_seconds * checked_out_license_quantity",
            "utilization_pct": "observed_peak_or_average_consumption / entitled_quantity * 100, only when comparable quantities and time windows are available",
            "potential_reclaim_quantity": "entitled_quantity - measured_peak_concurrent_usage, only after checking contract terms, deployment scope and business requirements"
        },
        "quality_rules": [
            "Do not count an OUT event as a completed session until a matching IN event is found or an explicit session-end rule is applied.",
            "Keep unmatched OUT events visible as open sessions; do not silently discard them.",
            "Do not allow negative session durations.",
            "Preserve the original event timestamp and timezone when known.",
            "Do not infer department from username or hostname unless an authoritative mapping is supplied.",
            "Keep feature names and license metrics distinct; a feature is not necessarily a purchasable license unit.",
            "Do not calculate monetary savings without an authorized unit price and valid reclaim quantity.",
            "Do not infer compliance from utilization alone; entitlement, deployment and contract rules are required."
        ],
        "limitations": [
            "The research papers are methodological references, not current organizational inventory or usage records.",
            "The papers do not provide current contract prices or enterprise entitlements.",
            "Session duration is not always equivalent to active application use."
        ]
    }
    dictionary_path = OUT / "licensing_data_dictionary.json"
    dictionary_path.write_text(json.dumps(dictionary, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "domain": "Licensing",
        "research_documents_processed": len(PDFS),
        "knowledge_documents_created": len(knowledge_docs),
        "extraction": extraction_summary,
        "outputs": [
            str(jsonl_path.relative_to(ROOT)),
            str(dictionary_path.relative_to(ROOT)),
            str((OUT / "license_inventory_template.csv").relative_to(ROOT)),
            str((OUT / "license_events_template.csv").relative_to(ROOT)),
            str((OUT / "license_cost_reference_template.csv").relative_to(ROOT))
        ],
        "note": "CSV files contain headers only. No enterprise license records or costs were fabricated."
    }
    (OUT / "licensing_build_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
