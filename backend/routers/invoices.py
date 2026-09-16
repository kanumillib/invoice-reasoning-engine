import io
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from lib.db import db
from models.invoice import (
    InvoiceFields,
    InvoiceProcessResponse,
    PurchaseOrder,
    ResetResponse,
    SampleInvoice,
    Summary,
)


router = APIRouter(prefix="/invoices", tags=["invoices"])

# These are source-document scenarios, not extracted results. Every sample is rendered
# into a PDF and then sent through the same extraction path as an uploaded file.
SAMPLE_INVOICES: dict[str, dict[str, Any]] = {
    "happy": {"label": "Happy path", "description": "Acme invoice inside PO tolerance", "render": "text", "lines": ["Vendor Name: Acme Corporation", "Invoice Number: INV-1001", "Invoice Date: 2025-02-14", "PO Reference: PO-1001", "Total Amount: $8,400.00"]},
    "split-1": {"label": "Split PO · 1 of 2", "description": "First half of a legitimate split bill", "render": "text", "lines": ["Vendor Name: Globex Industries", "Invoice Number: INV-2001", "Invoice Date: 2025-02-15", "PO Reference: PO-1002", "Total Amount: $5,000.00"]},
    "split-2": {"label": "Split PO · 2 of 2", "description": "Second half completes the same PO", "render": "text", "lines": ["Vendor Name: Globex Industries", "Invoice Number: INV-2002", "Invoice Date: 2025-02-16", "PO Reference: PO-1002", "Total Amount: $5,000.00"]},
    "over-tolerance": {"label": "Over tolerance", "description": "Amount lands above the PO ceiling", "render": "text", "lines": ["Vendor Name: Northstar Industrial", "Invoice Number: INV-3001", "Invoice Date: 2025-02-17", "PO Reference: PO-1003", "Total Amount: $10,200.00"]},
    "scanned": {"label": "Scanned / OCR", "description": "No text layer · real local Tesseract OCR", "render": "scanned", "lines": ["Vendor Name: Vertex Supplies", "Invoice Number: INV-4001", "Invoice Date: 2025-02-18", "Total Amount: $6,000.00"]},
    "missing-total": {"label": "Missing total", "description": "Critical amount field is absent", "render": "text", "lines": ["Vendor Name: Acme Corporation", "Invoice Number: INV-5001", "Invoice Date: 2025-02-19", "PO Reference: PO-1004"]},
    "duplicate": {"label": "Duplicate resubmission", "description": "Same invoice number as the happy path", "render": "text", "lines": ["Vendor Name: Acme Corporation", "Invoice Number: INV-1001", "Invoice Date: 2025-02-14", "PO Reference: PO-1001", "Total Amount: $8,400.00"]},
}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n:;|")
    return value or None


def _parse_amount(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"[-+]?\$?\s*([\d,]+(?:\.\d{1,2})?)", value)
    return float(match.group(1).replace(",", "")) if match else None


def _parse_text_fields(text: str) -> InvoiceFields:
    def field(pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return _clean(match.group(1)) if match else None

    amount_match = re.search(r"(?:total[ \t]*(?:amount|due)?|amount[ \t]*due)[ \t]*[:#-]?[ \t]*\$?[ \t]*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    date = field(r"(?:invoice[ \t]*date|date)[ \t]*[:#-]?[ \t]*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})")
    return InvoiceFields(
        vendor_name=field(r"vendor(?:[ \t]*name)?[ \t]*[:#-][ \t]*(.+)$"),
        invoice_number=field(r"invoice[ \t]*(?:number|no\.?|#)[ \t]*[:#-][ \t]*([A-Z0-9-]+)"),
        invoice_date=date,
        po_reference=field(r"\b(?:po|purchase[ \t]*order)(?:[ \t]*reference|[ \t]*number|[ \t]*no\.?)?[ \t]*[:#-][ \t]*([A-Z0-9-]+)"),
        total_amount=_parse_amount(amount_match.group(1) if amount_match else None),
    )


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        # A parse failure is treated as having no text layer; OCR gets the chance to read it.
        return ""


def _ocr_pdf_text(content: bytes) -> str:
    from pdf2image import convert_from_bytes
    import pytesseract

    images = convert_from_bytes(content, dpi=250, fmt="png", thread_count=1)
    return "\n".join(pytesseract.image_to_string(image, config="--psm 6") for image in images)


def _extract_fields_from_pdf(content: bytes) -> tuple[InvoiceFields, str]:
    text = _extract_pdf_text(content)
    if text.strip():
        return _parse_text_fields(text), "text_layer"
    try:
        ocr_text = _ocr_pdf_text(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"OCR could not process this scanned PDF: {exc}") from exc
    return _parse_text_fields(ocr_text), "ocr"


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_text_pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 18 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -34 Td")
        commands.append(f"({_pdf_escape(line)}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(pdf)


def _build_scanned_pdf(lines: list[str]) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(image)
    try:
        heading = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 64)
        body = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 44)
    except OSError:
        heading = body = ImageFont.load_default()
    draw.text((150, 160), "VENDOR INVOICE", fill="black", font=heading)
    y = 380
    for line in lines:
        draw.text((150, y), line, fill="black", font=body)
        y += 115
    output = io.BytesIO()
    image.save(output, format="PDF", resolution=150.0)
    return output.getvalue()


def _sample_pdf(key: str) -> bytes:
    sample = SAMPLE_INVOICES.get(key)
    if sample is None:
        raise HTTPException(status_code=400, detail="Unknown sample invoice")
    return _build_scanned_pdf(sample["lines"]) if sample["render"] == "scanned" else _build_text_pdf(sample["lines"])


async def _get_po(po_number: str) -> PurchaseOrder | None:
    document = await db.purchase_orders.find_one({"po_number": po_number})
    return PurchaseOrder(**document) if document else None


async def _find_match(fields: InvoiceFields) -> tuple[PurchaseOrder | None, str | None]:
    if fields.po_reference:
        po = await _get_po(fields.po_reference)
        return po, "po_reference" if po else None
    if fields.vendor_name and fields.total_amount is not None:
        candidates = await db.purchase_orders.find({"vendor_name": {"$regex": f"^{re.escape(fields.vendor_name)}$", "$options": "i"}}).to_list(100)
        for document in candidates:
            po = PurchaseOrder(**document)
            if abs(fields.total_amount - po.po_amount) / po.po_amount <= 0.05:
                return po, "vendor_amount"
    return None, None


async def _cumulative_for_po(po_number: str) -> float:
    rows = await db.invoices.find({"po_number": po_number, "reason_code": {"$ne": "duplicate"}}).to_list(1000)
    return sum(float(row.get("extracted", {}).get("total_amount") or 0) for row in rows)


async def _process_fields(fields: InvoiceFields, extraction_source: str) -> InvoiceProcessResponse:
    now = datetime.now(timezone.utc)
    base = {"extraction_source": extraction_source, "extracted": fields.model_dump(), "processed_at": now}

    if fields.total_amount is None or fields.invoice_number is None:
        response = InvoiceProcessResponse(**base, decision="flag", reason_code="missing_data", reason="Critical data is missing: invoice number and total amount are required before approval.")
        await db.invoices.insert_one({**response.model_dump(mode="json"), "po_number": None, "demo_seed": False})
        return response

    duplicate = await db.invoices.find_one({"extracted.invoice_number": fields.invoice_number, "extracted.vendor_name": fields.vendor_name, "reason_code": {"$ne": "duplicate"}})
    if duplicate:
        response = InvoiceProcessResponse(**base, decision="reject", reason_code="duplicate", reason=f"Invoice {fields.invoice_number} from {fields.vendor_name or 'this vendor'} was already processed; this resubmission is rejected.")
        await db.invoices.insert_one({**response.model_dump(mode="json"), "po_number": duplicate.get("po_number"), "demo_seed": False})
        return response

    matched_po, match_method = await _find_match(fields)
    if matched_po is None:
        reference = fields.po_reference or "the vendor and amount"
        response = InvoiceProcessResponse(**base, decision="reject", reason_code="no_po_match", reason=f"No purchase order matched {reference}; direct PO lookup and the vendor + 5% amount fallback both returned no result.")
        await db.invoices.insert_one({**response.model_dump(mode="json"), "po_number": None, "demo_seed": False})
        return response

    cumulative = await _cumulative_for_po(matched_po.po_number) + (fields.total_amount or 0)
    progress = round(cumulative / matched_po.po_amount * 100, 1)
    lower_bound = matched_po.po_amount * (1 - matched_po.tolerance_pct / 100)
    upper_bound = matched_po.po_amount * (1 + matched_po.tolerance_pct / 100)
    if cumulative > upper_bound:
        over_pct = round((cumulative - matched_po.po_amount) / matched_po.po_amount * 100, 1)
        decision, reason_code = "flag", "amount_mismatch"
        reason = f"Cumulative billed amount is ${cumulative:,.2f}, which is {over_pct:.1f}% over the PO amount and above its ±{matched_po.tolerance_pct:.1f}% tolerance ceiling."
    elif cumulative >= lower_bound:
        decision, reason_code = "approve", "within_tolerance"
        reason = f"Cumulative billed amount is ${cumulative:,.2f}, within the PO amount of ${matched_po.po_amount:,.2f} and its ±{matched_po.tolerance_pct:.1f}% tolerance."
    else:
        decision, reason_code = "pending", "partial"
        reason = f"Cumulative billed amount is ${cumulative:,.2f} of ${matched_po.po_amount:,.2f} ({progress:.1f}%). It is below the {100 - matched_po.tolerance_pct:.1f}% approval threshold; awaiting the remainder of this split PO."

    response = InvoiceProcessResponse(**base, matched_po=matched_po, match_method=match_method, cumulative_amount=round(cumulative, 2), progress_pct=progress, decision=decision, reason_code=reason_code, reason=reason)
    await db.invoices.insert_one({**response.model_dump(mode="json"), "po_number": matched_po.po_number, "demo_seed": False})
    return response


@router.get("/samples", response_model=list[SampleInvoice])
async def get_samples() -> list[SampleInvoice]:
    return [SampleInvoice(key=key, label=value["label"], description=value["description"]) for key, value in SAMPLE_INVOICES.items()]


@router.post("/process", response_model=InvoiceProcessResponse)
async def process_invoice(file: UploadFile | None = File(default=None), sample_key: str | None = Form(default=None)) -> InvoiceProcessResponse:
    if file is None and sample_key is None:
        raise HTTPException(status_code=400, detail="Upload a PDF or choose a sample invoice")

    if sample_key:
        if sample_key == "duplicate" and not await db.invoices.find_one({"extracted.invoice_number": "INV-1001", "extracted.vendor_name": "Acme Corporation", "reason_code": {"$ne": "duplicate"}}):
            happy_fields, happy_source = _extract_fields_from_pdf(_sample_pdf("happy"))
            await _process_fields(happy_fields, happy_source)
        fields, extraction_source = _extract_fields_from_pdf(_sample_pdf(sample_key))
        return await _process_fields(fields, extraction_source)

    if not file or not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF invoices are supported")
    content = await file.read()
    fields, extraction_source = _extract_fields_from_pdf(content)
    return await _process_fields(fields, extraction_source)


@router.get("/history", response_model=list[InvoiceProcessResponse])
async def get_history() -> list[InvoiceProcessResponse]:
    rows = await db.invoices.find({"demo_seed": {"$ne": True}}).sort("processed_at", -1).to_list(1000)
    results: list[InvoiceProcessResponse] = []
    for row in rows:
        if "extraction_source" not in row:
            row["extraction_source"] = "ocr" if row.get("extraction_method") == "ocr" else "text_layer"
        results.append(InvoiceProcessResponse(**{key: row[key] for key in InvoiceProcessResponse.model_fields if key in row}))
    return results


@router.get("/summary", response_model=Summary)
async def get_summary() -> Summary:
    rows = await db.invoices.find({"demo_seed": {"$ne": True}}).to_list(1000)
    counts = {"approve": 0, "flag": 0, "reject": 0, "pending": 0}
    for row in rows:
        if row.get("decision") in counts:
            counts[row["decision"]] += 1
    return Summary(total=len(rows), **counts)


@router.delete("/session", response_model=ResetResponse)
async def reset_session() -> ResetResponse:
    result = await db.invoices.delete_many({"demo_seed": {"$ne": True}})
    return ResetResponse(deleted=result.deleted_count)


@router.get("/pos", response_model=list[PurchaseOrder])
async def get_purchase_orders() -> list[PurchaseOrder]:
    rows = await db.purchase_orders.find().sort("po_number", 1).to_list(100)
    return [PurchaseOrder(**row) for row in rows]