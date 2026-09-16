export type Decision = "approve" | "flag" | "reject" | "pending";
export type ExtractionSource = "text_layer" | "ocr";

export interface PurchaseOrder {
  id: string;
  po_number: string;
  vendor_name: string;
  po_amount: number;
  tolerance_pct: number;
  status: string;
}

export interface InvoiceFields {
  vendor_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  po_reference: string | null;
  total_amount: number | null;
}

export interface InvoiceProcessResponse {
  id: string;
  extraction_source: ExtractionSource;
  extracted: InvoiceFields;
  matched_po: PurchaseOrder | null;
  match_method: "po_reference" | "vendor_amount" | null;
  cumulative_amount: number | null;
  progress_pct: number | null;
  decision: Decision;
  reason_code: string;
  reason: string;
  processed_at: string;
}

export interface SampleInvoice {
  key: string;
  label: string;
  description: string;
}

export interface Summary {
  total: number;
  approve: number;
  flag: number;
  reject: number;
  pending: number;
}

export interface ResetResponse {
  deleted: number;
}