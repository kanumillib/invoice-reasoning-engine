def test_extraction_fields_and_method(client):
    r = client.delete('/invoices/session'); assert r.status_code == 200, r.text[:200]
    r = client.post('/invoices/process', data={'sample_key': 'happy'})
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    assert b['extracted']['vendor_name'] == 'Acme Corporation'
    assert b['extracted']['invoice_number'] == 'INV-1001'
    assert b['extracted']['invoice_date'] == '2025-02-14'
    assert b['extracted']['po_reference'] == 'PO-1001'
    assert b['extracted']['total_amount'] == 8400
    assert b['extraction_method'] == 'text'
