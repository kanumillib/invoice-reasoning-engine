import uuid

from tests.conftest import build_text_pdf


def test_vendor_po_mismatch_rejected_before_amount_check(client):
    """A Globex invoice explicitly citing Acme's PO-1001 must be rejected as
    vendor_po_mismatch and must not fall through to amount_mismatch."""
    client.delete('/invoices/session')
    invoice_number = f"INV-tscheck-vm-{uuid.uuid4().hex[:8]}"
    pdf = build_text_pdf([
        "Vendor Name: Globex Industries",
        f"Invoice Number: {invoice_number}",
        "Invoice Date: 2025-03-01",
        "PO Reference: PO-1001",
        "Total Amount: $8,500.00",
    ])
    r = client.post('/invoices/process', files={'file': ('mismatch.pdf', pdf, 'application/pdf')})
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body['decision'] == 'reject'
    assert body['reason_code'] == 'vendor_po_mismatch'
    assert 'PO-1001' in body['reason']
    assert 'Acme Corporation' in body['reason']
    assert 'Globex Industries' in body['reason']
    assert body.get('cumulative_amount') is None


def test_vendor_mismatch_excluded_from_po_cumulative(client):
    """A rejected vendor-mismatch invoice against a PO must not count toward
    that PO's cumulative billed amount for later legitimate invoices."""
    client.delete('/invoices/session')

    acme_1 = build_text_pdf([
        "Vendor Name: Acme Corporation",
        f"Invoice Number: INV-tscheck-cum-a-{uuid.uuid4().hex[:8]}",
        "Invoice Date: 2025-03-02",
        "PO Reference: PO-1001",
        "Total Amount: $4,000.00",
    ])
    r1 = client.post('/invoices/process', files={'file': ('a1.pdf', acme_1, 'application/pdf')})
    assert r1.status_code == 200, r1.text[:300]
    b1 = r1.json()
    assert b1['matched_po']['po_number'] == 'PO-1001'
    assert b1['cumulative_amount'] == 4000.0

    globex_mismatch = build_text_pdf([
        "Vendor Name: Globex Industries",
        f"Invoice Number: INV-tscheck-cum-g-{uuid.uuid4().hex[:8]}",
        "Invoice Date: 2025-03-03",
        "PO Reference: PO-1001",
        "Total Amount: $50,000.00",
    ])
    r2 = client.post('/invoices/process', files={'file': ('g.pdf', globex_mismatch, 'application/pdf')})
    assert r2.status_code == 200, r2.text[:300]
    b2 = r2.json()
    assert b2['decision'] == 'reject'
    assert b2['reason_code'] == 'vendor_po_mismatch'
    assert b2.get('cumulative_amount') is None

    acme_2 = build_text_pdf([
        "Vendor Name: Acme Corporation",
        f"Invoice Number: INV-tscheck-cum-b-{uuid.uuid4().hex[:8]}",
        "Invoice Date: 2025-03-04",
        "PO Reference: PO-1001",
        "Total Amount: $4,200.00",
    ])
    r3 = client.post('/invoices/process', files={'file': ('a2.pdf', acme_2, 'application/pdf')})
    assert r3.status_code == 200, r3.text[:300]
    b3 = r3.json()
    assert b3['matched_po']['po_number'] == 'PO-1001'
    # 4000 + 4200 = 8200; the rejected $50,000 Globex invoice must not be included.
    assert b3['cumulative_amount'] == 8200.0
    assert b3['decision'] == 'approve'
    assert b3['reason_code'] == 'within_tolerance'
