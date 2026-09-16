def test_duplicate_rejected(client):
    client.delete('/invoices/session')
    first = client.post('/invoices/process', data={'sample_key':'happy'}); assert first.status_code == 200, first.text[:300]
    r = client.post('/invoices/process', data={'sample_key':'duplicate'}); assert r.status_code == 200, r.text[:300]
    b = r.json(); assert b['decision'] == 'reject'; assert b['reason_code'] == 'duplicate'; assert 'resubmission' in b['reason'].lower()
