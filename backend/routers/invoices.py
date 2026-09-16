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

SAMPLE_INVOICES: dict[str, dict[str, Any]] = {
    "happy": {
        "label": "Happy path",
        "description": "Acme invoice inside PO tolerance",
        "extraction_method": "text",
        "fields": {"vendor_name": "Acme Corporation", "invoice_number": "INV-1001", "invoice_date": "2025-02-14", "po_reference": "PO-1001", "total_amount": 8400.0},
    },
    "split-1": {
        "label": "Split PO · 1 of 2",
        "description": "First half of a legitimate split bill",
        "extraction_method": "text",
        "fields": {"vendor_name": "Globex Industries", "invoice_number": "INV-2001", "invoice_date": "2025-02-15", "po_reference": "PO-1002", "total_amount": 5000.0},
    },
    "split-2": {
        "label": "Split PO · 2 of 2",
        "description": "Second half completes the same PO",
        "extraction_method": "text",
        "fields": {"vendor_name": "Globex Industries", "invoice_number": "INV-2002", "invoice_date": "2025-02-16", "po_reference": "PO-1002", "total_amount": 5000.0},
    },
    "over-tolerance": {
        "label": "Over tolerance",
        "description": "Amount lands above the PO ceiling",
        "extraction_method": "text",
        "fields": {"vendor_name": "Northstar Industrial", "invoice_number": "INV-3001", "invoice_date": "2025-02-17", "po_reference": "PO-1003", "total_amount": 10200.0},
    },
    "scanned": {
        "label": "Scanned / OCR",
        "description": "No text layer · local OCR fallback",
        "extraction_method": "ocr",
        "fields": {"vendor_name": "Vertex Supplies", "invoice_number": "INV-4001", "invoice_date": "2025-02-18", "po_reference": None, "total_amount": 6000.0},
    },
    "missing-total": {
        "label": "Missing total",
        "description": "Critical amount field is absent",
        "extraction_method": "text",
        "fields": {"vendor_name": "Acme Corporation", "invoice_number": "INV-5001", "invoice_date": "2025-02-19", "po_reference": "PO-1004", "total_amount": None},
    },
    "duplicate": {
        "label": "Duplicate resubmission",
        "description": "Same invoice number as the happy path",
        "extraction_method": "text",
        "fields": {"vendor_name": "Acme Corporation", "invoice_number": "INV-1001", "invoice_date": "2025-02-14", "po_reference": "PO-1001", "total_amount": 8400.0},
    },
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

    amount_match = re.search(r"(?:total\s*(?:amount|due)?|amount\s*due)\s*[:#-]?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    date = field(r"(?:invoice\s*date|date)\s*[:#-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})")
    return InvoiceFields(
        vendor_name=field(r"vendor(?:\s*name)?\s*[:#-]\s*(.+)$"),
        invoice_number=field(r"invoice\s*(?:number|no\.?|#)\s*[:#-]\s*([A-Z0-9-]+)"),
        invoice_date=date,
        po_reference=field(r"(?:po|purchase\s*order)(?:\s*reference|\s*number|\s*no\.?)?\s*[:#-]\s*([A-Z0-9-]+)"),
        total_amount=_parse_amount(amount_match.group(1) if amount_match else None),
    )


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return content.decode("latin-1", errors="ignore")


def _has_extractable_fields(fields: InvoiceFields) -> bool:
    return any(value is not None for value in fields.model_dump().values())


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


async def _process_fields(fields: InvoiceFields, extraction_method: str) -> InvoiceProcessResponse:
    now = datetime.now(timezone.utc)
    base = {"extraction_method": extraction_method, "extracted": fields.model_dump(), "processed_at": now}

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


def _fields_from_sample(key: str) -> tuple[InvoiceFields, str]:
    sample = SAMPLE_INVOICES.get(key)
    if sample is None:
        raise HTTPException(status_code=400, detail="Unknown sample invoice")
    return InvoiceFields(**sample["fields"]), sample["extraction_method"]


@router.get("/samples", response_model=list[SampleInvoice])
async def get_samples() -> list[SampleInvoice]:
    return [SampleInvoice(key=key, label=value["label"], description=value["description"], extraction_method=value["extraction_method"]) for key, value in SAMPLE_INVOICES.items()]


@router.post("/process", response_model=InvoiceProcessResponse)
async def process_invoice(file: UploadFile | None = File(default=None), sample_key: str | None = Form(default=None)) -> InvoiceProcessResponse:
    if file is None and sample_key is None:
        raise HTTPException(status_code=400, detail="Upload a PDF or choose a sample invoice")

    if sample_key:
        fields, extraction_method = _fields_from_sample(sample_key)
        if sample_key == "duplicate" and not await db.invoices.find_one({"extracted.invoice_number": "INV-1001", "extracted.vendor_name": "Acme Corporation", "reason_code": {"$ne": "duplicate"}}):
            happy_fields, happy_method = _fields_from_sample("happy")
            await _process_fields(happy_fields, happy_method)
        return await _process_fields(fields, extraction_method)

    if not file or not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF invoices are supported")
    content = await file.read()
    text = _extract_pdf_text(content)
    fields = _parse_text_fields(text)
    extraction_method = "text" if _has_extractable_fields(fields) else "ocr"
    if extraction_method == "ocr":
        # The demo keeps OCR local and deterministic. A scanned sample is backed by the
        # same path; uploaded image-only PDFs still surface the OCR method and any text
        # hints that a local OCR engine can provide in a later deployment.
        fields = _parse_text_fields(content.decode("latin-1", errors="ignore"))
    return await _process_fields(fields, extraction_method)


@router.get("/history", response_model=list[InvoiceProcessResponse])
async def get_history() -> list[InvoiceProcessResponse]:
    rows = await db.invoices.find({"demo_seed": {"$ne": True}}).sort("processed_at", -1).to_list(1000)
    return [InvoiceProcessResponse(**{key: row[key] for key in InvoiceProcessResponse.model_fields if key in row}) for row in rows]


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