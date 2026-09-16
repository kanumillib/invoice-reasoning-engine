def test_happy_processes(client):
    reset = client.delete('/invoices/session')
    assert reset.status_code == 200, reset.text[:200]
    r = client.post('/invoices/process', data={'sample_key': 'happy'})
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body['decision'] == 'approve'
    assert body['reason_code'] == 'within_tolerance'
    assert body['matched_po']['po_number'] == 'PO-1001'
