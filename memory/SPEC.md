# Invoice-to-Decision Agent

## What it does
Processes vendor invoice PDFs or generated demo PDFs through extraction, PO matching, and ordered validation decisions. Text-layer PDFs are parsed directly; image-only PDFs are rasterized with Poppler and recognized offline by Tesseract. The live run view reveals those stages sequentially; the dashboard shows session history and counts.

## Data model
- `purchase_orders`: string id, PO number, vendor, amount, tolerance percentage, status.
- `invoices`: extracted invoice fields, actual extraction source (`text_layer` or `ocr`), matched PO, cumulative amount/progress, decision, reason code, human-readable reason, UTC processed timestamp.

## Decision order
Missing invoice number or total -> flag/missing_data; duplicate invoice number plus vendor -> reject/duplicate; no direct PO or vendor+5% match -> reject/no_po_match; explicit PO whose vendor differs from the invoice vendor -> reject/vendor_po_mismatch; cumulative matched-PO amount within tolerance -> approve/within_tolerance; over tolerance -> flag/amount_mismatch; under approval threshold -> pending/partial.

## Key flows
1. Choose one of seven samples or upload a PDF.
2. Watch Extraction, PO Matching, and Decision Rules stages appear in order.
3. Review fields, actual per-file extraction source, matched PO, cumulative progress, and explanation.
4. Open Dashboard for session history, counts, and seeded PO data.

## Auth
No authentication or roles. This is a local operational demo.

## OCR
Tesseract OCR is a real offline runtime dependency (`tesseract-ocr` + `pytesseract`) and Poppler rasterizes scanned PDFs (`pdf2image` + `poppler-utils`). Samples are rendered to PDFs and pass through the same parser; no OCR result is hardcoded or file-specific.