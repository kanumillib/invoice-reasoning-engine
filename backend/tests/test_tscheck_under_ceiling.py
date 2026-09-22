import uuid

from tests.conftest import build_text_pdf


def test_northstar_just_under_ceiling_approves(client):
    """A Northstar invoice for $9,900 against its own PO-1003 ($9,500 +/-5%,
    ceiling $9,975) must approve as within_tolerance."""
    client.delete('/invoices/session')
    invoice_number = f"INV-tscheck-uc-{uuid.uuid4().hex[:8]}"
    pdf = build_text_pdf([
        "Vendor Name: Northstar Industrial",
        f"Invoice Number: {invoice_number}",
        "Invoice Date: 2025-03-05",
        "PO Reference: PO-1003",
        "Total Amount: $9,900.00",
    ])
    r = client.post('/invoices/process', files={'file': ('under-ceiling.pdf', pdf, 'application/pdf')})
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body['matched_po']['po_number'] == 'PO-1003'
    assert body['cumulative_amount'] == 9900.0
    assert body['decision'] == 'approve'
    assert body['reason_code'] == 'within_tolerance'
