from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, Field


Decision = Literal["approve", "flag", "reject", "pending"]
ExtractionMethod = Literal["text", "ocr"]
ReasonCode = Literal["missing_data", "duplicate", "no_po_match", "amount_mismatch", "partial", "within_tolerance"]


class PurchaseOrder(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    po_number: str
    vendor_name: str
    po_amount: float
    tolerance_pct: float
    status: str


class InvoiceFields(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    po_reference: str | None = None
    total_amount: float | None = None


class InvoiceProcessResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    extraction_method: ExtractionMethod
    extracted: InvoiceFields
    matched_po: PurchaseOrder | None = None
    match_method: Literal["po_reference", "vendor_amount"] | None = None
    cumulative_amount: float | None = None
    progress_pct: float | None = None
    decision: Decision
    reason_code: ReasonCode
    reason: str
    processed_at: datetime


class SampleInvoice(BaseModel):
    key: str
    label: str
    description: str
    extraction_method: ExtractionMethod


class Summary(BaseModel):
    total: int
    approve: int
    flag: int
    reject: int
    pending: int


class ResetResponse(BaseModel):
    deleted: int